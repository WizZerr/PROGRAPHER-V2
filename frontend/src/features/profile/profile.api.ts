import { apiRequest } from "@/lib/api";

export type PhotographerSetupStatus =
  | "no_profile"
  | "data_review"
  | "training"
  | "needs_more_data"
  | "experimental"
  | "evaluated";

export type PhotographerSetupOverview = {
  lightroom: {
    detected: boolean;
    application_path: string | null;
    source: string | null;
  };
  discovered_catalogs: string[];
  discovered_presets: Array<{
    path: string;
    name: string;
  }>;
  setup: {
    source_type: "lightroom_catalog" | "edits_folder" | "none" | null;
    catalog_path: string | null;
    edits_folder_path: string | null;
    style_name: string | null;
    preset_path: string | null;
    camera_profile: string | null;
    color_profile_mode: "from_source" | "explicit";
    status: PhotographerSetupStatus;
    updated_at: string | null;
  };
  selected_catalog: {
    path: string;
    exists: boolean;
    readable: boolean;
    sqlite_valid: boolean;
    catalog_photo_records: number | null;
    note: string;
  } | null;
  selected_edits_folder: {
    path: string;
    exists: boolean;
    readable: boolean;
    xmp_files: number;
    note: string;
  } | null;
  readiness_reasons: string[];
};

export async function getPhotographerSetup(): Promise<PhotographerSetupOverview> {
  return apiRequest<PhotographerSetupOverview>("/api/photographer/setup");
}

export async function selectLightroomCatalog(
  path: string,
): Promise<PhotographerSetupOverview> {
  return apiRequest<PhotographerSetupOverview>(
    "/api/photographer/setup/catalog",
    {
      method: "POST",
      body: JSON.stringify({ path }),
    },
  );
}

export async function selectEditsFolder(
  path: string,
): Promise<PhotographerSetupOverview> {
  return apiRequest<PhotographerSetupOverview>(
    "/api/photographer/setup/edits-folder",
    {
      method: "POST",
      body: JSON.stringify({ path }),
    },
  );
}

export async function continueWithoutEditSource(): Promise<PhotographerSetupOverview> {
  return apiRequest<PhotographerSetupOverview>(
    "/api/photographer/setup/no-source",
    {
      method: "POST",
    },
  );
}

export async function saveStylePreferences(input: {
  style_name: string | null;
  preset_path: string | null;
  color_profile_mode: "from_source" | "explicit";
  camera_profile: string | null;
}): Promise<PhotographerSetupOverview> {
  return apiRequest<PhotographerSetupOverview>(
    "/api/photographer/setup/style",
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}
