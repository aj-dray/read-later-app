"use server";

import { clearSession, setSession } from "@/app/_lib/auth";
import { getServiceBaseUrl } from "@/app/_lib/utils";

export type AuthActionState =
  | { status: "idle" }
  | { status: "success" }
  | { status: "error"; message: string };

function extractCredentials(
  formData: FormData,
): { username: string; password: string } | { error: string } {
  const usernameValue = formData.get("username");
  const passwordValue = formData.get("password");

  const username =
    typeof usernameValue === "string" ? usernameValue.trim() : undefined;
  const password =
    typeof passwordValue === "string" ? passwordValue : undefined;

  if (!username || !password) {
    return { error: "Username and password are required." };
  }

  if (username.length < 3) {
    return { error: "Username must be at least 3 characters." };
  }

  if (password.length < 6) {
    return { error: "Password must be at least 6 characters." };
  }

  return { username, password };
}

function handleAuthError(message: string): AuthActionState {
  return { status: "error", message };
}

export async function signInAction(
  _prevState: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  const credentials = extractCredentials(formData);
  if ("error" in credentials) {
    return handleAuthError(credentials.error);
  }

  try {
    const response = await fetch(`${getServiceBaseUrl()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      let message = "Unable to sign in.";
      try {
        const data = (await response.json()) as { detail?: string };
        if (data?.detail) {
          message = data.detail;
        }
      } catch {
        // ignore JSON parse issues
      }
      return handleAuthError(message);
    }

    const payload = (await response.json()) as {
      access_token: string;
      token_type: string;
    };

    await setSession(payload.access_token);
  } catch (error) {
    console.error("Failed to sign in", error);
    return handleAuthError("Unexpected error during sign in.");
  }

  return { status: "success" };
}

export async function signUpAction(
  prevState: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  const credentials = extractCredentials(formData);
  if ("error" in credentials) {
    return handleAuthError(credentials.error);
  }

  try {
    const response = await fetch(`${getServiceBaseUrl()}/user/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      let message = "Unable to create account.";
      try {
        const data = (await response.json()) as { detail?: string };
        if (data?.detail) {
          message = data.detail;
        }
      } catch {
        // ignore JSON parse issues
      }
      return handleAuthError(message);
    }

    // After successful sign-up, sign in the user
    return await signInAction(prevState, formData);
  } catch (error) {
    console.error("Failed to sign up", error);
    return handleAuthError("Unexpected error during sign up.");
  }
}

export async function signOutAction(): Promise<void> {
  await clearSession();
}
