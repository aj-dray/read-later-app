"use server";

import { authedFetch } from "@/app/_lib/auth";

export type User = {
  user_id: string;
  username: string;
};

export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await authedFetch("/user/me");

    if (!response.ok) {
      // If unauthorized, don't log as error
      if (response.status === 401) {
        return null;
      }
      console.error("Failed to get current user:", response.status);
      return null;
    }

    const userData = (await response.json()) as User;
    return userData;
  } catch (error) {
    console.error("Failed to get current user:", error);
    return null;
  }
}
