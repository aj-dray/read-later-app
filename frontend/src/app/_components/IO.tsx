"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Dropdown option type
export interface DropdownOption {
  value: string;
  label: string;
}

// Props for the general dropdown component
export interface GeneralDropdownProps {
  options: DropdownOption[];
  selectedValue?: string;
  onSelect: (option: DropdownOption) => void;
  placeholder?: string;
  onDropdownStateChange?: (isOpen: boolean) => void;
  isOpen?: boolean;
}

// General reusable dropdown component
export function GeneralDropdown({
  options,
  selectedValue,
  onSelect,
  placeholder = "Select...",
  onDropdownStateChange,
  isOpen: externalIsOpen,
}: GeneralDropdownProps): React.JSX.Element {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen = externalIsOpen !== undefined ? externalIsOpen : internalIsOpen;
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const [portalContainer, setPortalContainer] = useState<HTMLElement | null>(
    null,
  );
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === selectedValue);

  const handleSelect = useCallback(
    (option: DropdownOption) => {
      onSelect(option);
      if (externalIsOpen === undefined) {
        setInternalIsOpen(false);
      }
      onDropdownStateChange?.(false);
      setFocusedIndex(-1);
    },
    [onSelect, onDropdownStateChange, externalIsOpen],
  );

  const handleToggle = useCallback(() => {
    // Only handle toggle if we're managing internal state
    if (externalIsOpen === undefined) {
      const newIsOpen = !internalIsOpen;
      setInternalIsOpen(newIsOpen);
      onDropdownStateChange?.(newIsOpen);

      if (newIsOpen) {
        // When opening, focus on selected option or first option
        const selectedIndex = options.findIndex(
          (opt) => opt.value === selectedValue,
        );
        setFocusedIndex(selectedIndex >= 0 ? selectedIndex : 0);
      } else {
        setFocusedIndex(-1);
      }
    }
  }, [
    externalIsOpen,
    internalIsOpen,
    options,
    selectedValue,
    onDropdownStateChange,
  ]);

  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        if (externalIsOpen === undefined) {
          setInternalIsOpen(false);
        }
        onDropdownStateChange?.(false);
        setFocusedIndex(-1);
      }
    },
    [externalIsOpen, onDropdownStateChange],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!isOpen) {
        return;
      }

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setFocusedIndex((prev) => (prev + 1) % options.length);
          break;
        case "ArrowUp":
          event.preventDefault();
          setFocusedIndex((prev) =>
            prev <= 0 ? options.length - 1 : prev - 1,
          );
          break;
        case "Enter":
          event.preventDefault();
          if (focusedIndex >= 0 && focusedIndex < options.length) {
            handleSelect(options[focusedIndex]);
          }
          break;
        case "Escape":
          event.preventDefault();
          if (externalIsOpen === undefined) {
            setInternalIsOpen(false);
          }
          onDropdownStateChange?.(false);
          setFocusedIndex(-1);
          break;
        default:
          break;
      }
    },
    [
      focusedIndex,
      handleSelect,
      isOpen,
      options,
      onDropdownStateChange,
      externalIsOpen,
    ],
  );

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleClickOutside, handleKeyDown, isOpen]);

  useEffect(() => {
    setPortalContainer(document.body);
  }, []);

  const getDropdownPosition = () => {
    if (!dropdownRef.current) return { top: 0, left: 0 };
    const rect = dropdownRef.current.getBoundingClientRect();
    return {
      top: rect.top,
      left: rect.left,
    };
  };

  return (
    <div className="relative inline-block">
      {/* Collapsed state - always visible */}
      <div
        className="w-[100px] h-[20px] rounded-[10px] cursor-pointer transition-all duration-200 ease-in-out overflow-visible flex items-center justify-end px-[10px]"
        onClick={externalIsOpen === undefined ? handleToggle : undefined}
        ref={dropdownRef}
      >
        <div className="text-right text-black/75 text-xs font-bold">
          {selectedOption?.label || placeholder}
        </div>
      </div>

      {isOpen &&
        portalContainer &&
        createPortal(
          <div
            className="fixed drop-shadow-md z-[9999] w-[100px] rounded-[10px] bg-[#B5B5B5]/75 backdrop-blur-2xl flex flex-col animate-dropdown-expand overflow-visible"
            style={getDropdownPosition()}
          >
            {options.map((option, index) => {
              const isFirst = index === 0;
              const isLast = index === options.length - 1;
              const isSelected = focusedIndex === index;

              return (
                <div
                  key={option.value}
                  className={`
                  w-full h-[20px] px-[7.5px]
                  ${isFirst ? "rounded-t-[10px]" : isLast ? "rounded-b-[10px]" : ""}
                  flex justify-end items-center
                  cursor-pointer
                  transition-all duration-150 ease-in-out
                  ${
                    isSelected
                      ? "bg-[#A0A0A0]/75 text-black/75"
                      : "bg-transparent text-black/75 hover:bg-[#B0B0B0]/75"
                  }
                `}
                  onMouseEnter={() => setFocusedIndex(index)}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    handleSelect(option);
                  }}
                >
                  <div className="text-right text-xs font-bold">
                    {option.label}
                  </div>
                </div>
              );
            })}
          </div>,
          portalContainer,
        )}
    </div>
  );
}

export type DropdownComponentProps = GeneralDropdownProps;

export function DropdownComponent({
  options,
  selectedValue,
  onSelect,
  placeholder,
  onDropdownStateChange,
  isOpen,
}: DropdownComponentProps): React.JSX.Element {
  return (
    <GeneralDropdown
      options={options}
      selectedValue={selectedValue}
      onSelect={onSelect}
      placeholder={placeholder}
      onDropdownStateChange={onDropdownStateChange}
      isOpen={isOpen}
    />
  );
}

// Props for the number input control
export interface NumberInputControlProps {
  value: number;
  min?: number;
  max?: number;
  onChange: (value: number) => void;
  onDropdownStateChange?: (isOpen: boolean) => void;
  isOpen?: boolean;
}

export function NumberInputControl({
  value,
  onChange,
  onDropdownStateChange,
  isOpen: externalIsOpen,
}: NumberInputControlProps): React.JSX.Element {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen = externalIsOpen !== undefined ? externalIsOpen : internalIsOpen;
  const [inputValue, setInputValue] = useState<string>(String(value));
  const inputRef = useRef<HTMLInputElement>(null);

  const floatPattern = /^-?\d*(\.\d*)?$/;

  const openEditor = useCallback(() => {
    if (externalIsOpen === undefined) setInternalIsOpen(true);
    onDropdownStateChange?.(true);
    setInputValue(String(value));
  }, [externalIsOpen, onDropdownStateChange, value]);

  const closeEditor = useCallback(() => {
    if (externalIsOpen === undefined) setInternalIsOpen(false);
    onDropdownStateChange?.(false);
  }, [externalIsOpen, onDropdownStateChange]);

  const commit = useCallback(() => {
    const normalized = inputValue.replace(",", ".");
    const num = Number.parseFloat(normalized);
    if (Number.isFinite(num)) {
      onChange(num);
    }
    closeEditor();
  }, [inputValue, onChange, closeEditor]);

  const cancel = useCallback(() => {
    setInputValue(String(value));
    closeEditor();
  }, [value, closeEditor]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        commit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancel();
      }
    },
    [commit, cancel],
  );

  return (
    <div
      className="w-[100px] h-[20px] rounded-[10px] cursor-pointer flex items-center justify-end px-[5px]"
      onClick={!isOpen ? openEditor : undefined}
      onMouseDownCapture={(e) => e.stopPropagation()}
    >
      {isOpen ? (
        <input
          ref={inputRef}
          autoFocus
          type="text"
          inputMode="decimal"
          className="w-full h-full rounded-[10px] bg-[#B0B0B0] text-right text-black/75 text-xs font-bold px-[10px] outline-none shadow-md"
          value={inputValue}
          onChange={(e) => {
            const next = e.target.value;
            if (next === "" || floatPattern.test(next.replace(",", "."))) {
              setInputValue(next);
            }
          }}
          onKeyDown={handleKeyDown}
          onBlur={commit}
        />
      ) : (
        <div className="text-right text-black/75 text-xs font-bold">
          {value}
        </div>
      )}
    </div>
  );
}
