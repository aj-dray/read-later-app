"use server";

import { authedFetch } from "@/app/_lib/auth";

export type UserControlStates = Record<string, unknown>;

/**
 * Get a specific user setting
 */
export async function getUserSetting(
  settingType: string,
  settingKey: string,
): Promise<Record<string, unknown>> {
  try {
    const response = await authedFetch(
      `/user/settings/${encodeURIComponent(settingType)}/${encodeURIComponent(settingKey)}`,
    );

    if (!response.ok) {
      console.warn(
        `Failed to get user setting ${settingType}/${settingKey}:`,
        response.statusText,
      );
      return {};
    }

    const data = await response.json();
    return data.setting_value || {};
  } catch (error) {
    console.warn(
      `Error getting user setting ${settingType}/${settingKey}:`,
      error,
    );
    return {};
  }
}

/**
 * Get control states for the current user on a specific page
 */
export async function getUserControls(
  pagePath: string,
): Promise<UserControlStates> {
  return await getUserSetting("controls", pagePath);
}

/**
 * Set a user setting
 */
export async function setUserSetting(
  settingType: string,
  settingKey: string,
  settingValue: Record<string, unknown>,
): Promise<boolean> {
  try {
    const response = await authedFetch(
      `/user/settings/${encodeURIComponent(settingType)}/${encodeURIComponent(settingKey)}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(settingValue),
      },
    );

    return response.ok;
  } catch (error) {
    console.warn(
      `Error setting user setting ${settingType}/${settingKey}:`,
      error,
    );
    return false;
  }
}

/**
 * Set all control states for the current user on a specific page
 */
export async function setUserControls(
  pagePath: string,
  controlStates: UserControlStates,
): Promise<boolean> {
  return await setUserSetting("controls", pagePath, controlStates);
}

/**
 * Update a single field within a user setting
 */
export async function updateUserSettingField(
  settingType: string,
  settingKey: string,
  fieldKey: string,
  fieldValue: unknown,
): Promise<boolean> {
  try {
    const response = await authedFetch(
      `/user/settings/${encodeURIComponent(settingType)}/${encodeURIComponent(settingKey)}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          field_key: fieldKey,
          field_value: fieldValue,
        }),
      },
    );

    return response.ok;
  } catch (error) {
    console.warn(
      `Error updating user setting field ${settingType}/${settingKey}/${fieldKey}:`,
      error,
    );
    return false;
  }
}

/**
 * Update a single control state for the current user on a specific page
 */
export async function updateUserControl(
  pagePath: string,
  controlKey: string,
  controlValue: unknown,
): Promise<boolean> {
  return await updateUserSettingField(
    "controls",
    pagePath,
    controlKey,
    controlValue,
  );
}
