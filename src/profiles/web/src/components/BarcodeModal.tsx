import { useState, useEffect, useRef } from "react";
import { X, Copy, Check, Plus, Trash2, Hash, Download } from "lucide-react";
import { generateBarcode } from "../api/client";

interface BarcodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialFilePath?: string;
  md5?: string;
}

interface KeyValuePair {
  key: string;
  value: string;
}

export function BarcodeModal({ isOpen, onClose, initialFilePath, md5 }: BarcodeModalProps) {
  const [barcodeImage, setBarcodeImage] = useState<string | null>(null);
  const [rawContent, setRawContent] = useState<string>("");
  const [pairs, setPairs] = useState<KeyValuePair[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedImage, setCopiedImage] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  // Initialize from file path or content
  useEffect(() => {
    if (!isOpen) return;

    async function init() {
      if (initialFilePath) {
        setLoading(true);
        try {
          const res = await generateBarcode({ filePath: initialFilePath });
          setBarcodeImage(res.image);
          setRawContent(res.content);
          parseContentToPairs(res.content);
        } catch (err: any) {
          setError(err.message);
        } finally {
          setLoading(false);
        }
      }
    }
    init();
  }, [isOpen, initialFilePath]);

  const parseContentToPairs = (content: string) => {
    const newPairs = content.split(";").map(p => {
      const parts = p.split("=");
      return { key: parts[0] || "", value: parts[1] || "" };
    }).filter(p => p.key || p.value);
    setPairs(newPairs);
  };

  const updateBarcode = async (currentPairs: KeyValuePair[]) => {
    const content = currentPairs
      .filter(p => p.key.trim())
      .map(p => `${p.key.trim()}=${p.value.trim()}`)
      .join(";");
    
    setRawContent(content);
    
    if (!content) {
      setBarcodeImage(null);
      return;
    }

    try {
      const res = await generateBarcode({ content });
      setBarcodeImage(res.image);
    } catch (err: any) {
      console.error("Failed to re-generate barcode:", err);
    }
  };

  const handlePairChange = (index: number, field: keyof KeyValuePair, value: string) => {
    const newPairs = [...pairs];
    newPairs[index][field] = value;
    setPairs(newPairs);
    void updateBarcode(newPairs);
  };

  const addPair = () => {
    const newPairs = [...pairs, { key: "", value: "" }];
    setPairs(newPairs);
  };

  const removePair = (index: number) => {
    const newPairs = pairs.filter((_, i) => i !== index);
    setPairs(newPairs);
    void updateBarcode(newPairs);
  };

  const addMd5 = () => {
    if (!md5 || pairs.some(p => p.key.toLowerCase() === "md5")) return;
    const newPairs = [...pairs, { key: "md5", value: md5 }];
    setPairs(newPairs);
    void updateBarcode(newPairs);
  };

  const handleSave = () => {
    if (!barcodeImage) return;
    const link = document.createElement("a");
    link.href = barcodeImage;
    link.download = `profiles-qr-${new Date().getTime()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const copyText = async () => {
    try {
      await navigator.clipboard.writeText(rawContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Copy failed", err);
    }
  };

  const copyImage = async () => {
    if (!barcodeImage) return;
    try {
      const res = await fetch(barcodeImage);
      const blob = await res.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ [blob.type]: blob })
      ]);
      setCopiedImage(true);
      setTimeout(() => setCopiedImage(false), 2000);
    } catch (err) {
      console.error("Image copy failed", err);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        ref={modalRef}
        className="w-full max-w-md rounded-xl border border-frame-line glass-panel p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink">QR Code Settings</h3>
          <button onClick={onClose} className="focus-ring rounded-md p-1 text-ink-muted hover:bg-elevated hover:text-ink">
            <X className="h-4 w-4" />
          </button>
        </div>

        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          </div>
        ) : error ? (
          <div className="rounded-md border border-status-danger-border bg-status-danger-bg p-4 text-center text-xs text-status-danger-text">
            {error}
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-col items-center gap-4">
              <div className="relative group">
                <div className="h-48 w-48 overflow-hidden rounded-lg border border-line bg-white p-2">
                  {barcodeImage ? (
                    <img src={barcodeImage} alt="QR Code" className="h-full w-full object-contain" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-slate-400">No content</div>
                  )}
                </div>
                {barcodeImage && (
                  <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/20 rounded-lg">
                    <button 
                      onClick={copyImage}
                      className="focus-ring flex items-center gap-2 rounded-md bg-white/90 p-2 text-xs font-medium text-slate-900 shadow-sm hover:bg-white"
                    >
                      {copiedImage ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                      {copiedImage ? "Copied" : "Copy Image"}
                    </button>
                  </div>
                )}
              </div>
              
              <div className="flex w-full gap-2">
                <button
                  onClick={copyText}
                  className="btn btn-secondary flex-1 px-3 py-1.5"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-status-success-text" /> : <Copy className="h-3.5 w-3.5" />}
                  Copy Content
                </button>
                <button
                  onClick={handleSave}
                  disabled={!barcodeImage}
                  className="btn btn-primary flex-1 px-3 py-1.5"
                >
                  <Download className="h-3.5 w-3.5" />
                  Save Image
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-ink-muted uppercase tracking-wider">Payload Fields</label>
                <div className="flex gap-2">
                  {md5 && !pairs.some(p => p.key === "md5") && (
                    <button
                      onClick={addMd5}
                      className="btn-chip flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold text-chip-purple-text border border-chip-purple-border"
                    >
                      <Hash className="h-3 w-3" /> Inc. MD5
                    </button>
                  )}
                  <button
                    onClick={addPair}
                    className="btn-chip flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold text-chip-indigo-text border border-chip-indigo-border"
                  >
                    <Plus className="h-3 w-3" /> Add Field
                  </button>
                </div>
              </div>

              <div className="max-h-48 space-y-2 overflow-y-auto pr-1 custom-scrollbar">
                {pairs.map((pair, index) => (
                  <div key={index} className="flex gap-2 items-center slide-in">
                    <input
                      type="text"
                      placeholder="key"
                      value={pair.key}
                      onChange={(e) => handlePairChange(index, "key", e.target.value)}
                      className="w-1/3 rounded border border-line bg-elevated px-2 py-1 text-xs text-ink focus:border-indigo-500 focus:outline-none"
                    />
                    <input
                      type="text"
                      placeholder="value"
                      value={pair.value}
                      onChange={(e) => handlePairChange(index, "value", e.target.value)}
                      className="flex-1 rounded border border-line bg-elevated px-2 py-1 text-xs text-ink focus:border-indigo-500 focus:outline-none"
                    />
                    <button
                      onClick={() => removePair(index)}
                      className="p-1 text-ink-muted hover:text-status-danger-text transition-colors"
                      aria-label="Remove field"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                {pairs.length === 0 && (
                  <p className="text-center py-4 text-xs text-ink-muted italic">No fields defined</p>
                )}
              </div>
            </div>

            <div className="pt-2 border-t border-line">
              <label className="text-[10px] font-medium text-ink-muted uppercase tracking-wider block mb-1.5">Raw Preview</label>
              <div className="rounded bg-elevated p-2 font-mono text-[10px] text-ink-secondary break-all border border-line">
                {rawContent || <span className="italic text-ink-muted/50">empty</span>}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
