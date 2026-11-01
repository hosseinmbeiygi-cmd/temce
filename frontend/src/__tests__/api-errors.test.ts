// FE-13 — طبقه‌بندی خطاهای انتقال: لغو، اتمام زمان، احراز هویت.

import { describe, expect, it } from "vitest";

import {
  API_ERROR_MESSAGES,
  ApiError,
  ApiTimeoutError,
  ApiUnauthorizedError,
  apiErrorUserMessage,
  describeApiError,
  getApiErrorStatus,
  isAbortError,
  isRetryableApiError,
  isTimeoutError,
  isUnauthorizedError,
} from "@/lib/api-errors";

describe("api-errors — classification", () => {
  it("recognizes DOMException and Element-style AbortError instances", () => {
    expect(isAbortError(new DOMException("Aborted", "AbortError"))).toBe(true);
    const err = new Error("aborted");
    err.name = "AbortError";
    expect(isAbortError(err)).toBe(true);
    expect(isAbortError(new Error("boom"))).toBe(false);
  });

  it("recognizes the dedicated timeout and unauthorized types", () => {
    expect(isTimeoutError(new ApiTimeoutError("/slow", 60_000))).toBe(true);
    expect(isTimeoutError(new ApiError("HTTP 500", { status: 500 }))).toBe(false);
    expect(isUnauthorizedError(new ApiUnauthorizedError("HTTP 401"))).toBe(true);
    expect(isUnauthorizedError(new ApiError("nope", { status: 401 }))).toBe(true);
    expect(isUnauthorizedError(new ApiError("nope", { status: 403 }))).toBe(false);
  });

  it("reads the HTTP status off plain transport errors", () => {
    expect(getApiErrorStatus(new ApiError("HTTP 503", { status: 503 }))).toBe(503);
    expect(getApiErrorStatus(new Error("HTTP 500"))).toBeNull();
  });
});

describe("api-errors — user-facing copy", () => {
  it("never shows a message for a cancelled request", () => {
    expect(apiErrorUserMessage(new DOMException("Aborted", "AbortError"))).toBe("");
  });

  it("explains timeouts, expired sessions and outages in Persian", () => {
    expect(apiErrorUserMessage(new ApiTimeoutError("/slow", 60_000))).toBe(API_ERROR_MESSAGES.timeout);
    expect(apiErrorUserMessage(new ApiUnauthorizedError("HTTP 401"))).toBe(API_ERROR_MESSAGES.unauthorized);
    expect(apiErrorUserMessage(new ApiError("HTTP 500", { status: 500 }))).toBe(API_ERROR_MESSAGES.server);
    expect(apiErrorUserMessage(new TypeError("Failed to fetch"))).toBe(API_ERROR_MESSAGES.network);
    expect(apiErrorUserMessage(new Error("weird"), "fallback")).toBe("fallback");
  });

  it("passes backend validation text through but hides transport jargon", () => {
    expect(describeApiError(new ApiError("HTTP 422: نماد نامعتبر است", { status: 422 }))).toBe(
      "HTTP 422: نماد نامعتبر است",
    );
    expect(describeApiError(new ApiTimeoutError("/slow", 60_000))).toBe(API_ERROR_MESSAGES.timeout);
    expect(describeApiError(new DOMException("Aborted", "AbortError"), "fallback")).toBe("");
    expect(describeApiError(undefined, "fallback")).toBe("fallback");
  });
});

describe("api-errors — retry policy", () => {
  it("does not retry cancellations, timeouts or auth failures", () => {
    expect(isRetryableApiError(new DOMException("Aborted", "AbortError"))).toBe(false);
    expect(isRetryableApiError(new ApiTimeoutError("/slow", 60_000))).toBe(false);
    expect(isRetryableApiError(new ApiUnauthorizedError("HTTP 401"))).toBe(false);
    expect(isRetryableApiError(new ApiError("HTTP 403", { status: 403 }))).toBe(false);
    expect(isRetryableApiError(new ApiError("HTTP 404", { status: 404 }))).toBe(false);
  });

  it("retries transient network and server failures", () => {
    expect(isRetryableApiError(new TypeError("Failed to fetch"))).toBe(true);
    expect(isRetryableApiError(new ApiError("HTTP 500", { status: 500 }))).toBe(true);
    expect(isRetryableApiError(new ApiError("HTTP 429", { status: 429 }))).toBe(true);
    expect(isRetryableApiError(new ApiError("HTTP 200 envelope", { status: null }))).toBe(true);
  });
});
