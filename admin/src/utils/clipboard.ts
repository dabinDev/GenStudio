// 管理后台通用剪贴板复制。优先用 navigator.clipboard，失败时回退到 textarea + execCommand。
// 返回是否复制成功，由调用方决定 toast 文案。

export async function copyText(text: string): Promise<boolean> {
  if (!text) {
    return false;
  }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // 忽略，走下面的兜底方案。
  }
  try {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.top = '-9999px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.focus();
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  } catch {
    return false;
  }
}
