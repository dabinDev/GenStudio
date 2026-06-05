"use client";

interface JsonViewerProps {
  title: string;
  value: unknown;
}

export function JsonViewer({ title, value }: JsonViewerProps) {
  return (
    <details className="raw-panel">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
