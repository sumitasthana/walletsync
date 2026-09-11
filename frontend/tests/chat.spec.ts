import { expect, test } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";

const card = (name: string) => ({
  card_id: name,
  card_name: name,
  bank: "chase",
  reward_currency: "Cash Back",
  annual_fee_usd: 0,
  foreign_transaction_fee_pct: 3,
  has_image: false,
  score: 3,
  matched: [
    { category: "gas", rate: 3, cap_usd: null, requires_activation: false },
  ],
});

test("Disney trip includes the no-fee Disney Visa and labels its rewards correctly", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("textbox")
    .fill("I want to go to Disney -- which card would fit");
  await expect(page.locator(".card-result")).toHaveCount(6);
  await expect(page.locator(".card-result .bank-label").first()).toHaveText(
    "pnc",
  );
  const disney = page.locator(".card-result").filter({
    has: page.getByRole("heading", {
      name: "Disney® Visa® Card",
      exact: true,
    }),
  });
  await page.locator(".more-matches > summary").click();
  await expect(disney).toHaveCount(1);
  await expect(disney).toContainText("No annual fee");
  await expect(disney).toContainText("1%");
  await expect(disney).toContainText("Earned in Disney Rewards Dollars");
});

test("card questions show names and focus on fit", async ({ page }) => {
  let sentMessage = "";
  await page.route("**/api/match", (route) =>
    route.fulfill({
      json: {
        matches: [
          {
            ...card("Marriott Bonvoy Boundless"),
            card_id: "marriott-bonvoy-boundless-58772b",
            annual_fee_usd: null,
            foreign_transaction_fee_pct: null,
          },
        ],
      },
    }),
  );
  await page.route("**/api/chat", (route) => {
    sentMessage = route.request().postDataJSON().message;
    return route.fulfill({
      json: {
        reply: "Let's compare the benefits for your spending.",
        cards: [],
        source: "live",
      },
    });
  });
  await page.goto("/");
  await page.getByRole("textbox").fill("hotel stays");
  await expect(page.locator(".card-result")).toHaveCount(1);
  await page.locator(".card-result summary").click();
  await expect(page.locator(".card-result")).not.toContainText("unavailable");
  await page.getByRole("button", { name: "Ask about this card" }).click();
  await expect(page.locator(".assistant")).toHaveCount(1);
  expect(sentMessage).toContain("Marriott Bonvoy Boundless");
  expect(sentMessage).toContain("my spending needs");
  expect(sentMessage).not.toContain("marriott-bonvoy-boundless-58772b");
  await expect(page.locator(".user")).not.toContainText("58772b");
});

test("desktop welcome, local matches, details and accessible help", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your spending. A card that gets it." }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/desktop-welcome.png" });
  await page.getByRole("button", { name: /The everyday essentials/ }).click();
  await expect(page.locator(".card-result")).toHaveCount(6);
  await page.locator(".card-result summary").first().click();
  await expect(
    page.getByRole("button", { name: "Ask about this card" }).first(),
  ).toBeVisible();
  await expect(page.locator(".reward").first()).toContainText("%");
  await page.screenshot({ path: "test-results/desktop-matches.png" });
  await page.getByRole("button", { name: "How WalletSync works" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "How WalletSync works" }),
  ).toBeFocused();
  expect(errors).toEqual([]);
});

test("neutral welcome, focus card first and a spending impact summary", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".welcome")).not.toContainText("Chase");
  await expect(page.locator(".welcome")).not.toContainText("PNC");
  await page.getByRole("textbox").fill("gas and groceries");
  await expect(page.locator(".card-result")).toHaveCount(6);
  await expect(page.locator(".card-result .bank-label").first()).toHaveText(
    "pnc",
  );
  await expect(page.locator(".card-heading")).not.toContainText([
    "TOP MATCH",
    "MATCH 02",
    "MATCH 03",
    "MATCH 04",
    "MATCH 05",
    "MATCH 06",
  ]);
  await expect(page.locator(".card-result:visible")).toHaveCount(2);
  await expect(page.locator(".takeaway-text")).toBeVisible();
  await page.locator(".tradeoff-details > summary").click();
  await expect(page.locator(".comparison-summary")).toBeInViewport();
  await expect(page.locator(".impact.positive").first()).toContainText(
    "per $100",
  );
  await expect(page.locator(".impact.negative").first()).toContainText(
    "per $100",
  );
  await page.screenshot({ path: "test-results/comparison-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".comparison-summary")).toBeInViewport();
  await page.screenshot({ path: "test-results/comparison-mobile.png" });
  await page.getByRole("textbox").fill("");
  await expect(page.locator(".comparison-summary")).toHaveCount(0);
});

test("safe messages, conversation history, keyboard entry and reset", async ({
  page,
}) => {
  const requests: { message: string; history: unknown[] }[] = [];
  await page.route("**/api/chat", (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        reply:
          '**A clear answer.** <img src=x onerror="window.injected=true"> [bad](javascript:alert(1))',
        cards: [card("Agent card")],
        source: "agent",
      },
    });
  });
  await page.goto("/");
  const input = page.getByRole("textbox");
  await input.fill(
    '<img src=x onerror="window.injected=true"> gas & groceries',
  );
  await input.press("Enter");
  await expect(page.locator(".assistant")).toHaveCount(1);
  await expect(page.locator(".assistant .visual-response")).toHaveCount(1);
  await page.getByText("More about your question", { exact: true }).click();
  await expect(page.locator(".assistant .message-body strong")).toHaveText(
    "A clear answer.",
  );
  await expect(page.locator(".message-body img")).toHaveCount(0);
  expect(await page.evaluate(() => "injected" in window)).toBe(false);
  await expect(page.locator(".visual-response h2")).toContainText(
    "Your card matches",
  );
  await input.fill("What about fees?");
  await input.press("Shift+Enter");
  await expect(input).toHaveValue("What about fees?\n");
  await input.press("Enter");
  await expect(page.locator(".assistant")).toHaveCount(2);
  expect(requests[0].history).toHaveLength(0);
  expect(requests[1].history).toHaveLength(2);
  await page.screenshot({ path: "test-results/desktop-chat.png" });
  await page.getByRole("button", { name: "New chat" }).click();
  await expect(page.locator(".message")).toHaveCount(0);
  await expect(page.locator(".card-result")).toHaveCount(0);
  await expect(input).toBeFocused();
});

test("older matches cannot replace a newer draft or agent results", async ({
  page,
}) => {
  // Deliberately ignore AbortSignal to verify the revision guard as well as cancellation.
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    window.fetch = (input, options) =>
      String(input).endsWith("/api/match")
        ? original(input, { ...options, signal: undefined })
        : original(input, options);
  });
  let releaseOld!: () => void;
  let releaseNext!: () => void;
  const oldGate = new Promise<void>((resolve) => {
    releaseOld = resolve;
  });
  const nextGate = new Promise<void>((resolve) => {
    releaseNext = resolve;
  });
  let oldStarted = false;
  let nextStarted = false;
  await page.route("**/api/match", async (route) => {
    const { text } = route.request().postDataJSON();
    if (text === "gas") {
      oldStarted = true;
      await oldGate;
    }
    if (text === "travel") {
      nextStarted = true;
      await nextGate;
    }
    await route.fulfill({ json: { matches: [card(text)] } });
  });
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      json: {
        reply: "Your match.",
        cards: [card("Agent card")],
        source: "agent",
      },
    }),
  );
  await page.goto("/");
  const input = page.getByRole("textbox");
  await input.fill("gas");
  await expect.poll(() => oldStarted).toBe(true);
  await input.fill("groceries");
  await expect(page.locator(".card-result h3")).toHaveText("groceries");
  releaseOld();
  await expect(page.locator(".card-result h3")).toHaveText("groceries");
  await input.fill("travel");
  await expect.poll(() => nextStarted).toBe(true);
  await input.press("Enter");
  await expect(page.locator(".card-result h3")).toHaveText("Agent card");
  releaseNext();
  await expect(page.locator(".card-result h3")).toHaveText("Agent card");
});

test("failure keeps live cards, supports retry and does not duplicate the user message", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/chat", (route) => {
    requests += 1;
    return route.fulfill(
      requests === 1
        ? {
            status: 503,
            json: {
              error: "The assistant is unavailable.",
              cards: [card("Live card")],
              source: "live",
              reply: "",
            },
          }
        : { json: { reply: "Recovered.", cards: [], source: "live" } },
    );
  });
  await page.goto("/");
  await page.getByRole("textbox").fill("gas");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(page.locator(".card-result h3")).toHaveText("Live card");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.locator(".assistant")).toContainText("Recovered.");
  await expect(page.locator(".user")).toHaveCount(1);
  await expect(page.locator(".card-result")).toHaveCount(0);
});

test("new chat cancels an in-flight answer", async ({ page }) => {
  let release!: () => void;
  let started = false;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/chat", async (route) => {
    started = true;
    await gate;
    await route.fulfill({
      json: { reply: "Old answer", cards: [], source: "live" },
    });
  });
  await page.goto("/");
  await page.getByRole("textbox").fill("gas");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect.poll(() => started).toBe(true);
  await expect(page.getByRole("textbox")).toBeDisabled();
  await page.getByRole("button", { name: "New chat" }).click();
  release();
  await expect(page.locator(".welcome")).toBeVisible();
  await expect(page.locator(".message")).toHaveCount(0);
  await expect(page.getByRole("textbox")).toBeEnabled();
});

test("mobile panels, touch layout and no horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.screenshot({ path: "test-results/mobile-welcome.png" });
  await page.getByRole("button", { name: /The everyday essentials/ }).click();
  await expect(page.locator(".card-result")).toHaveCount(6);
  await expect(page.locator(".card-result").first()).toBeVisible();
  await expect(page.locator(".card-result:visible")).toHaveCount(2);
  const shortlist = await page.locator(".visual-response").boundingBox();
  expect(shortlist!.height).toBeLessThan(600);
  await expect(page.locator(".more-matches > summary")).toBeInViewport();
  await page.screenshot({ path: "test-results/mobile-matches.png" });
  await expect(page.getByRole("textbox")).toBeVisible();
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
});

test("welcome and populated cards meet automated accessibility checks", async ({
  page,
}) => {
  await page.goto("/");
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.getByRole("textbox").fill("gas");
  await expect(page.locator(".card-result")).toHaveCount(6);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});

test("visual answers stay with each question and history excludes presentation data", async ({
  page,
}) => {
  const histories: { role: string; content: string; cards?: unknown }[][] = [];
  await page.route("**/api/chat", (route) => {
    const request = route.request().postDataJSON();
    histories.push(request.history);
    return route.fulfill({
      json: {
        reply: "Additional context for your question.",
        cards: [card(request.message === "gas" ? "Gas card" : "Travel card")],
        source: "agent",
      },
    });
  });
  await page.goto("/");
  await page.getByRole("textbox").fill("gas");
  await page.getByRole("textbox").press("Enter");
  await expect(page.locator(".assistant .visual-response")).toHaveCount(1);
  await expect(page.locator(".assistant .message-body")).not.toBeVisible();
  await expect(page.locator(".matches-panel")).toHaveCount(0);
  await page.getByRole("textbox").fill("travel");
  await page.getByRole("textbox").press("Enter");
  await expect(page.locator(".assistant .visual-response")).toHaveCount(2);
  await expect(page.locator(".assistant .card-result h3")).toHaveText([
    "Gas card",
    "Travel card",
  ]);
  expect(histories[1]).toEqual([
    { role: "user", content: "gas" },
    { role: "assistant", content: "Additional context for your question." },
  ]);
  await page.screenshot({ path: "test-results/visual-conversation.png" });
});
