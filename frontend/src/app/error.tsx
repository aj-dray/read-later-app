"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Optionally log the error to an error reporting service
    // console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen w-full items-center bg-[#F0F0F0] justify-center p-6">
      <div className="text-center">
        <h1 className="mb-2 text-2xl font-semibold text-gray-600">
          Something went wrong
        </h1>
        <p className="text-gray-500">
          The app couldn’t load data from the server.
        </p>
      </div>
    </div>
  );
}


