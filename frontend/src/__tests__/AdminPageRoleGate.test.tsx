// W5-01 — /admin باید نقش داشته باشد: کاربر عادی نباید پوستهٔ پنل را ببیند.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

const mockReplace = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  usePathname: () => "/admin",
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: (...args: unknown[]) => mockUseAuth(...args),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: undefined, isLoading: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/hooks/useSyncSettings", () => ({ useSyncSettings: () => [{}, vi.fn()] }));
vi.mock("next/dynamic", () => ({ default: () => () => <div /> }));

import AdminPage from "@/app/admin/page";

function auth(overrides: Record<string, unknown>) {
  return {
    isLoading: false,
    isAuthenticated: true,
    hasRole: (role: string) => role === "admin",
    hasAnyRole: () => true,
    user: { username: "u", roles: ["admin"] },
    logout: vi.fn(),
    ...overrides,
  };
}

describe("admin page role gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("denies a non-admin user with a 403-style panel instead of the admin shell", () => {
    mockUseAuth.mockReturnValue(auth({ hasRole: () => false, user: { username: "u", roles: ["user"] } }));

    render(<AdminPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(/دسترسی غیرمجاز/);
    expect(screen.queryByRole("button", { name: /همگام‌سازی/ })).not.toBeInTheDocument();
  });

  it("redirects an anonymous visitor to the login page", () => {
    mockUseAuth.mockReturnValue(auth({ isAuthenticated: false, hasRole: () => false, user: null }));

    const { container } = render(<AdminPage />);

    expect(mockReplace).toHaveBeenCalledWith("/auth/login?redirect=%2Fadmin");
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the admin shell for an admin", () => {
    mockUseAuth.mockReturnValue(auth({}));

    render(<AdminPage />);

    expect(screen.getByRole("button", { name: /همگام‌سازی/ })).toBeInTheDocument();
  });
});
