import MobileAddPanel from "@/app/_components/MobileAddPanel";
import MobileUserPanel from "@/app/_components/MobileUserPanel";
import { getSession } from "@/app/_lib/auth";
import { getCurrentUser } from "@/app/_lib/user";
import { redirect } from "next/navigation";

export default async function MobilePage() {
  const session = await getSession();
  const user = session ? await getCurrentUser() : null;

  if (!session) {
    redirect("/login");
  }

  return (
    <div className="flex flex-col justify-center items-center h-screen overflow-hidden bg-[#F0F0F0] p-[25px] gap-[25px]">
      <div className="w-full max-w-md">
        <MobileAddPanel />
      </div>
      <div className="flex-1 w-full max-w-md flex items-center justify-center text-center text-[#666]">
        <p>
          You can add items here, but viewing and managing your queue is only available on desktop.
        </p>
      </div>
      {session && (
        <div className="flex justify-center items-center w-full max-w-md pb-4">
          <MobileUserPanel username={user?.username ?? session.username ?? "Account"} />
        </div>
      )}
    </div>
  );
}
