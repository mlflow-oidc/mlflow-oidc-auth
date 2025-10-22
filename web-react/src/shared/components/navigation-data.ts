export type NavLinkData = {
  label: string;
  href: string;
};

export type NavigationData = {
  mainLinks: NavLinkData[];
  userControls: NavLinkData[];
};

export const getNavigationData = (userName: string): NavigationData => ({
  mainLinks: [
    { label: "MLFlow", href: "#" },
    { label: "GitHub", href: "#" },
    { label: "Docs", href: "#" },
  ],
  userControls: [
    { label: `Hello, ${userName}`, href: "#" },
    { label: "Logout", href: "#" },
  ],
});
