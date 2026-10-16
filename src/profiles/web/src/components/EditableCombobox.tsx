import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { ChevronDown } from "lucide-react";

interface EditableComboboxProps {
  id: string;
  ariaLabel: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
  optionLabel?: (value: string) => string;
}

export function EditableCombobox({
  id,
  ariaLabel,
  value,
  options,
  onChange,
  placeholder,
  className = "",
  inputClassName = "",
  optionLabel = (option) => option,
}: EditableComboboxProps) {
  const listboxId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);

  const filteredOptions = options.filter((option) =>
    optionLabel(option).toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  );
  const activeOptionId = activeIndex >= 0 && filteredOptions[activeIndex]
    ? `${listboxId}-option-${activeIndex}`
    : undefined;

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  const openList = () => {
    setQuery("");
    setActiveIndex(-1);
    setIsOpen(true);
  };

  const selectOption = (option: string) => {
    onChange(option);
    setQuery("");
    setActiveIndex(-1);
    setIsOpen(false);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!isOpen) {
        openList();
        setActiveIndex(0);
        return;
      }
      setActiveIndex((index) => Math.min(index + 1, filteredOptions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!isOpen) {
        openList();
        setActiveIndex(filteredOptions.length - 1);
        return;
      }
      setActiveIndex((index) => (index <= 0 ? filteredOptions.length - 1 : index - 1));
    } else if (event.key === "Enter" && isOpen && filteredOptions[activeIndex] !== undefined) {
      event.preventDefault();
      selectOption(filteredOptions[activeIndex]);
    } else if (event.key === "Escape") {
      setIsOpen(false);
    }
  };

  return (
    <div
      ref={containerRef}
      onBlur={(event) => {
        if (!containerRef.current?.contains(event.relatedTarget as Node | null)) {
          setIsOpen(false);
        }
      }}
      className={`relative flex min-w-0 ${className}`}
    >
      <input
        id={id}
        type="text"
        role="combobox"
        aria-label={ariaLabel}
        aria-autocomplete="list"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-activedescendant={activeOptionId}
        value={value}
        placeholder={placeholder}
        onFocus={openList}
        onChange={(event) => {
          onChange(event.target.value);
          setQuery(event.target.value);
          setActiveIndex(-1);
          setIsOpen(true);
        }}
        onKeyDown={handleKeyDown}
        className={`min-w-0 flex-1 rounded-l-md border border-line bg-elevated px-3 py-1.5 text-ink outline-none transition-colors hover:bg-surface-strong focus:border-indigo-500 ${inputClassName}`}
      />
      <button
        type="button"
        aria-label={`Show ${ariaLabel.toLowerCase()} options`}
        aria-expanded={isOpen}
        title={`Show ${ariaLabel.toLowerCase()} options`}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => (isOpen ? setIsOpen(false) : openList())}
        className="shrink-0 rounded-r-md border border-l-0 border-line bg-elevated px-2 text-ink-muted hover:bg-surface-strong hover:text-ink focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 transition-colors"
      >
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>
      {isOpen && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label={`${ariaLabel} options`}
          className="absolute left-0 top-full z-[60] mt-1 max-h-60 w-full min-w-48 overflow-y-auto rounded-md border border-line bg-surface py-1 text-ink shadow-xl"
        >
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option, index) => {
              const label = optionLabel(option);
              const isActive = index === activeIndex;
              const isSelected = option === value;
              return (
                <li
                  id={`${listboxId}-option-${index}`}
                  key={`${option}-${index}`}
                  role="option"
                  aria-selected={isSelected}
                  title={label || undefined}
                  onMouseEnter={() => setActiveIndex(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectOption(option)}
                  className={`cursor-pointer truncate px-3 py-1.5 ${
                    isActive ? "bg-elevated text-ink" : "text-ink-secondary"
                  } ${isSelected ? "font-semibold" : ""}`}
                >
                  {label || "(No filter)"}
                </li>
              );
            })
          ) : (
            <li className="px-3 py-1.5 text-ink-muted">No matching presets</li>
          )}
        </ul>
      )}
    </div>
  );
}