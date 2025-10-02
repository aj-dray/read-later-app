"use client";

import {
  useState,
  KeyboardEvent as ReactKeyboardEvent,
  useActionState,
  useTransition,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { usePathname } from "next/navigation";
import { addItemAction, type AddItemActionState } from "@/app/_actions/items";

export type AddedItemDetail = {
  itemId: string;
  url: string;
  error?: string;
};

type AddPanelProps = {
  onItemAdded?: (detail: AddedItemDetail) => void;
};

export default function AddPanel({ onItemAdded }: AddPanelProps) {
  const [isActive, setIsActive] = useState(false);
  const [url, setUrl] = useState("");
  const [isPending, startTransition] = useTransition();
  const [state, formAction] = useActionState<AddItemActionState, FormData>(
    addItemAction,
    { status: "idle" },
  );
  const lastSubmittedUrlRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pathname = usePathname();
  const isQueuePage = pathname === "/queue";

  const handleSubmit = () => {
    const trimmed = url.trim();
    if (!trimmed || isPending) {
      return;
    }

    const formData = new FormData();
    formData.append("url", trimmed);
    lastSubmittedUrlRef.current = trimmed;

    startTransition(() => {
      formAction(formData);
    });
  };

  const handleKeyDown = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  useEffect(() => {
    if (state.status === "idle") {
      return;
    }

    if (state.status === "success") {
      const detail: AddedItemDetail = {
        itemId: state.itemId,
        url: lastSubmittedUrlRef.current ?? "",
      };

      setUrl("");
      setIsActive(false);
      lastSubmittedUrlRef.current = null;

      onItemAdded?.(detail);

      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("queue:item-added", { detail }));
      }
    } else if (state.status === "error") {
      // Create a fake item ID for error items
      const fakeItemId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      const detail: AddedItemDetail = {
        itemId: fakeItemId,
        url: lastSubmittedUrlRef.current ?? "",
        error: `Error: ${state.message}`,
      };

      setUrl("");
      setIsActive(false);
      lastSubmittedUrlRef.current = null;

      onItemAdded?.(detail);

      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("queue:item-added", { detail }));
      }
    }
  }, [state, onItemAdded]);

  const handleInputFocus = () => {
    setIsActive(true);
  };

  const handleInputBlur = () => {
    if (!url.trim()) {
      setIsActive(false);
    }
  };

  const handleGlobalPaste = useCallback(
    async (e: Event) => {
      // Only respond to Ctrl+V or Command+V (Mac)
      if (isQueuePage && !isActive) {
        if (
          e instanceof globalThis.KeyboardEvent &&
          e.key === "v" &&
          (e.ctrlKey || e.metaKey)
        ) {
          e.preventDefault();
        } else if (e.type === "paste") {
          e.preventDefault();
        } else {
          return;
        }

        try {
          const clipboardText = await navigator.clipboard.readText();
          if (clipboardText) {
            setIsActive(true);
            setUrl(clipboardText);
            // Focus the input after a short delay to ensure it's rendered
            setTimeout(() => {
              inputRef.current?.focus();
            }, 10);
          }
        } catch (error) {
          console.error("Failed to read clipboard:", error);
        }
      }
    },
    [isQueuePage, isActive],
  );

  useEffect(() => {
    // Only add event listeners on the queue page
    if (!isQueuePage) return;

    // Add event listeners for paste events
    document.addEventListener("keydown", handleGlobalPaste);
    document.addEventListener("paste", handleGlobalPaste);

    return () => {
      document.removeEventListener("keydown", handleGlobalPaste);
      document.removeEventListener("paste", handleGlobalPaste);
    };
  }, [handleGlobalPaste, isQueuePage]);

  return (
    <div
      className={`w-full h-[40px] bg-white rounded-[20px] flex items-center justify-end relative transition-all duration-300 ease-in-out hover:scale-105 hover:drop-shadow-md ${
        isActive ? "scale-105 drop-shadow-md" : ""
      }`}
      style={{ transition: "all 300ms cubic-bezier(0.4, 0, 0.2, 1)" }}
    >
      {!isActive ? (
        <div
          className="flex items-center justify-center w-full h-full cursor-pointer "
          onClick={handleInputFocus}
        >
          <span className="text-[#A39E9E] font-medium text-[12px] text-center leading-[14.5px] ">
            + add item with url
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-[5px] px-[5px] w-full h-full">
          <div className="flex px-[15px] items-center">
            <input
              type="text"
              value={url}
              ref={inputRef}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setIsActive(false);
                  return;
                }
                handleKeyDown(e);
              }}
              onFocus={handleInputFocus}
              onBlur={handleInputBlur}
              placeholder="ctrl-v to paste"
              className="w-full bg-transparent text-[#A39E9E] font-medium items-center text-[12px] leading-[12px] outline-none placeholder-[#A39E9E]"
              autoFocus
              disabled={isPending}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={!url.trim() || isPending}
            className="w-[36px] h-[30px] bg-blue-400/50 rounded-[20px] flex items-center justify-center hover:bg-blue-400 transition-all duration-300 ease-in-out hover:scale-105 hover:drop-shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ transition: "all 300ms cubic-bezier(0.4, 0, 0.2, 1)" }}
          >
            <span className="text-[#242424] font-bold text-[12px] leading-[14.5px]">
              {isPending ? "..." : "⏎"}
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
