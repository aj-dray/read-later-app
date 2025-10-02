import { redirect } from "next/navigation";

import { getSession } from "@/app/_lib/auth";
import { getCurrentUser } from "@/app/_lib/user";

import AuthForms from "./AuthForms";

export default async function LoginPage() {
  const session = await getSession();
  console.log("Login page - session:", session);
  if (session) {
    // Verify session is valid with backend before redirecting
    const user = await getCurrentUser();
    if (user) {
      console.log("Session exists, redirecting to queue");
      redirect("/queue");
    }
    console.log("Session token exists but backend rejected it");
  }

  return (
    <div className="relative flex min-h-screen items-start justify-center bg-[#F0F0F0] p-6 overflow-hidden">
      <div className="w-full max-w-xs relative z-10 mt-[30vh]">
        <AuthForms />
      </div>
    </div>
  );
}
