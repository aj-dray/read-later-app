"use client";

import { useState } from "react";
import { signOutAction } from "@/app/login/actions";
import { useRouter } from "next/navigation";

type UserPanelProps = {
  username: string;
};

export default function UserPanel({ username }: UserPanelProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const router = useRouter();

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await signOutAction();
      router.push("/login");
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <div
      className={`panel-dark flex items-center justify-center gap-[10px] rounded-[20px] p-[15px] h-[40px] w-full cursor-pointer transition-all duration-300 ease-in-out hover:font-bold hover:drop-shadow-lg hover:scale-105 hover:!text-white !text-black ${
        isHovered ? "!bg-red-600" : ""
      }`}
      style={{
        transition: "all 300ms cubic-bezier(0.4, 0, 0.2, 1)",
        backgroundColor: isHovered ? "#dc2626" : "",
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={isHovered ? handleLogout : undefined}
    >
      {/* Username/Logout Text */}
      <span
        className="font-medium text-[12px] leading-[14.5px] text-center min-w-[75px] transition-all duration-300 ease-in-out"
        style={{
          transform: isLoggingOut ? "scale(0.95)" : "scale(1)",
          opacity: isLoggingOut ? 0.7 : 1,
          transition: "all 300ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        {isLoggingOut ? "Logging out..." : isHovered ? "Logout" : username}
      </span>

      {/* User Icon */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        className="transition-all duration-300 ease-in-out"
        style={{
          transform: isHovered
            ? "rotate(5deg) scale(1.1)"
            : "rotate(0deg) scale(1)",
          transition: "transform 300ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        <circle cx="12" cy="6" r="4" fill="currentColor" />
        <path
          fill="currentColor"
          d="M20 17.5c0 2.485 0 4.5-8 4.5s-8-2.015-8-4.5S7.582 13 12 13s8 2.015 8 4.5"
        />
      </svg>
    </div>
  );
}
