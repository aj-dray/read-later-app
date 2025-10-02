"use server";

import { authedFetch } from "@/app/_lib/auth";
import { normalizePagePath } from "@/app/_lib/path-utils";

export type UserControlStates = Record<string, unknown>;

/**
 * Server-side function to get a user setting
 */
export async function getUserSettingServer(
  settingType: string,
  settingKey: string,
): Promise<Record<string, unknown>> {
  try {
    const response = await authedFetch(
      `/user/settings/${encodeURIComponent(settingType)}/${encodeURIComponent(settingKey)}`,
    );

    if (!response.ok) {
      // If user is not authenticated or API fails, return empty object
      // Frontend will use defaults
      return {};
    }

    const data = await response.json();
    return data.setting_value || {};
  } catch (error) {
    // On any error, return empty object so frontend uses defaults
    console.warn(
      `Error loading user setting ${settingType}/${settingKey}:`,
      error,
    );
    return {};
  }
}

/**
 * Server-side function to get control states for the current user on a specific page
 * This runs during SSR/SSG to provide immediate control values without client-side loading
 */
export async function getUserControlsServer(
  pathname: string,
): Promise<UserControlStates> {
  const pagePath = normalizePagePath(pathname);
  return await getUserSettingServer("controls", pagePath);
}

/**
 * Get user setting with defaults merged in
 * This provides a complete set of setting values for immediate use
 */
export async function getUserSettingWithDefaults(
  settingType: string,
  settingKey: string,
  defaults: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const userSetting = await getUserSettingServer(settingType, settingKey);
  return { ...defaults, ...userSetting };
}

/**
 * Get control states with defaults merged in
 * This provides a complete set of control values for immediate use
 */
export async function getUserControlsWithDefaults(
  pathname: string,
  defaults: UserControlStates,
): Promise<UserControlStates> {
  const pagePath = normalizePagePath(pathname);
  return await getUserSettingWithDefaults("controls", pagePath, defaults);
}

/**
 * Pre-load user settings for multiple keys
 * Useful for prefetching settings
 */
export async function preloadUserSettings(
  settingType: string,
  settingKeys: string[],
): Promise<Record<string, Record<string, unknown>>> {
  const results: Record<string, Record<string, unknown>> = {};

  await Promise.allSettled(
    settingKeys.map(async (settingKey) => {
      const setting = await getUserSettingServer(settingType, settingKey);
      results[settingKey] = setting;
    }),
  );

  return results;
}

/**
 * Pre-load control states for multiple pages
 * Useful for prefetching controls for navigation
 */
export async function preloadUserControls(
  pathnames: string[],
): Promise<Record<string, UserControlStates>> {
  const normalizedPaths = pathnames.map(normalizePagePath);
  const results = await preloadUserSettings("controls", normalizedPaths);

  // Convert back to original pathname keys for backward compatibility
  const mappedResults: Record<string, UserControlStates> = {};
  pathnames.forEach((pathname, index) => {
    mappedResults[normalizedPaths[index]] = results[normalizedPaths[index]];
  });

  return mappedResults;
}

/**
 * Pre-load all app settings for global context
 * Gets settings for all known pages with their defaults
 */
export async function preloadAllAppSettings(): Promise<
  Record<string, UserControlStates>
> {
  const appPages = ["/queue", "/search", "/graph"];
  return await preloadUserControls(appPages);
}
