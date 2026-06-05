import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-title-block">
        <div className="header-kicker">
          <p className="eyebrow">Workbench</p>
          <span className="mini-status">BaseURL / API Key / Model</span>
        </div>
        <h2>{title}</h2>
        <p className="muted">{description}</p>
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}
