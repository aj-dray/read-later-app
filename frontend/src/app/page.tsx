import { redirect } from "next/navigation";

import { getSession } from "@/app/_lib/auth";

export default async function Page() {
  const session = await getSession();
  if (session) {
    redirect("/queue");
  }

  redirect("/login");
}
