/** What the server reports about an uploaded PDF. */
export interface UploadResult {
  id: string;
  pages: number;
  counts: NavigationCounts;
}

/** The things a seal must not destroy. Shown before and after so it is provable. */
export interface NavigationCounts {
  links: number;
  jumps: number;
  web: number;
  bookmarks: number;
}

/** One buyer: the text written into their copy, and what their file is called. */
export interface SealRow {
  text: string;
  filename: string;
}

export interface SealJob {
  id: string;
  visible: boolean;
  rows: SealRow[];
}
