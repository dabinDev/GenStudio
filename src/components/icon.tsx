"use client";

import type { LucideIcon } from "lucide-react";

interface IconTextProps {
  icon: LucideIcon;
  children: string;
}

export function IconText({ icon: Icon, children }: IconTextProps) {
  return (
    <span className="icon-text">
      <Icon aria-hidden="true" size={16} strokeWidth={2} />
      <span>{children}</span>
    </span>
  );
}
