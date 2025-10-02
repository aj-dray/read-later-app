"use client";

import { usePathname } from "next/navigation";
import Panel from "@/app/_components/Panel";
import { ReactNode } from "react";

type PanelSession = { user_id: string; username: string } | null;

type PanelGateProps = {
  children?: ReactNode;
  session: PanelSession;
};

export default function PanelGate({ children, session }: PanelGateProps) {
  const pathname = usePathname();

  if (pathname === "/mobile") {
    return null;
  }

  return <Panel session={session}>{children}</Panel>;
}


