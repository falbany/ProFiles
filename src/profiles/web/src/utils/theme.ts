/** Session theme resolution shared by launch init and dropped-config trials.

Mirrors the startup rule: only "light" is light — everything else
(including "auto" and unknown values) is dark.
 */
export function resolveSessionTheme(theme: string | undefined): "dark" | "light" {
  return theme === "light" ? "light" : "dark";
}
