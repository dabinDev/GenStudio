export type ModelActionMenuPlacement = "down" | "up";

export type TriggerBounds = Pick<DOMRect, "bottom" | "top">;

export function toggledModelActionMenuId(currentId: string, targetId: string): string {
  return currentId === targetId ? "" : targetId;
}

export function modelActionMenuPlacement(
  trigger: TriggerBounds,
  viewportHeight: number,
  menuHeight = 180,
): ModelActionMenuPlacement {
  const spaceBelow = viewportHeight - trigger.bottom;
  const spaceAbove = trigger.top;
  return spaceBelow < menuHeight && spaceAbove > spaceBelow ? "up" : "down";
}
