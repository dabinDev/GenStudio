export function isProductionRuntime(mode = import.meta.env.MODE, env = import.meta.env.VITE_GENSTUDIO_ENV): boolean {
  const value = (env || mode || "").toLowerCase();
  return value === "production" || value === "prod";
}

export function shouldShowDevAuth(
  mode = import.meta.env.MODE,
  env = import.meta.env.VITE_GENSTUDIO_ENV,
  flag = import.meta.env.VITE_ENABLE_DEV_AUTH,
): boolean {
  if (flag === "true") return true;
  if (flag === "false") return false;
  return !isProductionRuntime(mode, env);
}
