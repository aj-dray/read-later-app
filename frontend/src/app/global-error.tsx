"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body>
        <div className="flex min-h-screen w-full items-centerbg-[#F0F0F0]  justify-center p-6">
          <div className="text-center">
            <h1 className="mb-2 text-2xl font-semibold text-gray-600">
              Something went wrong
            </h1>
            <p className="text-gray-500">The app couldn’t load.</p>
          </div>
        </div>
      </body>
    </html>
  );
}


