"use client";

import {
  useState,
  KeyboardEvent,
  useActionState,
  useTransition,
  useEffect,
  useRef,
} from "react";
import { addItemAction, type AddItemActionState } from "@/app/_actions/items";

export type AddedItemDetail = {
  itemId: string;
  url: string;
  error?: string;
};

type AddPanelProps = {
  onItemAdded?: (detail: AddedItemDetail) => void;
};

export default function MobileAddPanel({ onItemAdded }: AddPanelProps) {
  const [isActive, setIsActive] = useState(false);
  const [url, setUrl] = useState("");
  const [isPending, startTransition] = useTransition();
  const [state, formAction] = useActionState<AddItemActionState, FormData>(
    addItemAction,
    { status: "idle" },
  );
  const lastSubmittedUrlRef = useRef<string | null>(null);

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

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
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

  return (
    <div
      className={`w-full h-[50px] bg-white rounded-[25px] flex items-center justify-end relative transition-all duration-300 ease-in-out hover:scale-105 hover:drop-shadow-md ${
        isActive ? "scale-105" : ""
      }`}>
      {!isActive ? (
        <div
          className="flex items-center justify-center w-full h-full cursor-pointer"
          onClick={handleInputFocus}
        >
          <span className="text-[#A39E9E] font-medium text-[16px] text-center leading-[18px]">
            + add item with url
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-[5px] px-[5px] w-full h-full">
          <div className="flex px-[15px] items-center w-full">
            <input
              type="text"
              value={url}
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
              placeholder="paste url here"
              className="w-full bg-transparent text-[#333] font-medium items-center text-[16px] leading-[18px] outline-none placeholder-[#A39E9E]"
              autoFocus
              disabled={isPending}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={!url.trim() || isPending}
            className="w-[60px] h-[40px] bg-blue-400/50 rounded-[20px] flex items-center justify-center hover:bg-blue-400 transition-all duration-300 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
          >
            <span className="text-[#242424] font-bold text-[14px] leading-[16px]">
              {isPending ? "..." : "⏎"}
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
