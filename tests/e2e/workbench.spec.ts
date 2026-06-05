import { expect, test } from "@playwright/test";

test("图片创作工作台可正常打开", async ({ page }) => {
  await page.goto("/images");

  await expect(page.getByText("CreativePannel")).toBeVisible();
  await expect(page.getByRole("button", { name: "+ 新建对话" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "GPT Image 1" })).toBeVisible();
  await expect(page.getByPlaceholder("描述你要生成的画面、风格、构图、材质、镜头感...")).toBeVisible();
});
