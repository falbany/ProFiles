import { FileCode } from "lucide-react";
import type { ScannedFileItem } from "../api/types";

interface FileListTableProps {
  files: ScannedFileItem[];
  columnHeaders: string[];
  columnNames: string[];
  selectedIndex: number;
  onSelectIndex: (idx: number) => void;
  onLaunch: (file: ScannedFileItem) => void;
  rowColors: [string, string][];
}

export function FileListTable({
  files,
  columnHeaders,
  columnNames,
  selectedIndex,
  onSelectIndex,
  onLaunch,
  rowColors,
}: FileListTableProps) {
  const headers = columnHeaders.length > 0 ? columnHeaders : ["File"];
  const keys = columnNames.length > 0 ? columnNames : ["File"];

  // Match row background tint based on filename patterns
  const getRowStyle = (filename: string, isSelected: boolean) => {
    if (isSelected) {
      return "bg-indigo-950/70 text-indigo-200 border-l-2 border-indigo-500";
    }
    for (const [pattern, color] of rowColors) {
      if (filename.toLowerCase().includes(pattern.toLowerCase())) {
        return `hover:bg-slate-800/60 text-slate-200 border-l-2 border-[${color}]`;
      }
    }
    return "hover:bg-slate-800/40 text-slate-300";
  };

  return (
    <div className="flex-1 overflow-auto bg-slate-950 text-xs">
      <table className="w-full border-collapse text-left">
        <thead className="sticky top-0 z-10 border-b border-slate-800 bg-slate-900 font-medium text-slate-400">
          <tr>
            <th className="w-8 px-3 py-2"></th>
            {headers.map((h, i) => (
              <th key={i} className="px-3 py-2">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-850">
          {files.length === 0 ? (
            <tr>
              <td colSpan={headers.length + 1} className="p-8 text-center text-slate-500">
                No matching files found. Click "Scan" to refresh.
              </td>
            </tr>
          ) : (
            files.map((file, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <tr
                  key={file.path || idx}
                  onClick={() => onSelectIndex(idx)}
                  onDoubleClick={() => onLaunch(file)}
                  className={`cursor-pointer transition-colors ${getRowStyle(file.filename, isSelected)}`}
                >
                  <td className="px-3 py-2 text-slate-500">
                    <FileCode className="h-3.5 w-3.5 text-slate-400" />
                  </td>
                  {keys.map((key, kIdx) => (
                    <td key={kIdx} className="px-3 py-2 font-mono">
                      {file.column_values[key] || (key === "File" ? file.filename : "-")}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
