"use client";

import type { ComponentType } from "react";
import { useState, cloneElement, isValidElement } from "react";

export default function ControlsFallback() {
  return null;
}

type ControlStripProps<P> = {
  label: string;
  io: ComponentType<P>;
  ioProps?: P;
};

export function ControlStrip<P extends Record<string, unknown>>({
  label,
  io: IOComp,
  ioProps,
}: ControlStripProps<P>) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const handleStripClick = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  const enhancedProps = {
    ...ioProps,
    onDropdownStateChange: setIsDropdownOpen,
    isOpen: isDropdownOpen,
  } as P & {
    onDropdownStateChange: typeof setIsDropdownOpen;
    isOpen: boolean;
  };

  return (
    <div
      className={`flex h-[30px] w-full items-center justify-between rounded-[15px] px-[5px] gap-[10px] transition-colors duration-200 hover:bg-black/10 cursor-pointer group ${isDropdownOpen ? "bg-black/10" : ""}`}
      onClick={handleStripClick}
    >
      <div className="min-w-[50px] text-left text-[#555555] text-[11px] font-bold px-[12.5px]">
        {label}
      </div>
      <div className="flex rounded-[10px] h-[20px] transition-colors duration-200 items-center justify-center">
        {/*group-hover:bg-[#B5B5B5]/75 group-hover:shadow-md */}
        <IOComp {...enhancedProps} />
      </div>
    </div>
  );
}
