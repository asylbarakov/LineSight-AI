import { expect, it } from "vitest";
import { loginFailureText, validateLogin } from "./login";

it("focuses the first missing field without treating password whitespace as empty", () => {
  expect(validateLogin("  ", "secret")?.field).toBe("username");
  expect(validateLogin("engineer", "")?.field).toBe("password");
  expect(validateLogin("engineer", " ")).toBeNull();
});
it("provides safe authentication, transport and server failure messages", () => {
  expect(loginFailureText(401)).toContain("Неверный логин или пароль");
  expect(loginFailureText(0)).toContain("соединение");
  expect(loginFailureText(429)).toContain("попыток");
  expect(loginFailureText(500)).toContain("Повторите");
  expect(loginFailureText(undefined)).toBe(loginFailureText(500));
});
