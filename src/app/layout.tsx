import type { Metadata } from "next";
import type { PropsWithChildren } from "react";

import { AppShell } from "@/components/app-shell";
import { WorkbenchProvider } from "@/components/workbench-provider";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "CreativePannel 工作台",
  description: "用于调试文案、图片、视频模型的本地多模型工作台。",
};

export default function RootLayout({ children }: PropsWithChildren) {
  return (
    <html lang="zh-CN">
      <body>
        <WorkbenchProvider>
          <AppShell>{children}</AppShell>
        </WorkbenchProvider>
      </body>
    </html>
  );
}
