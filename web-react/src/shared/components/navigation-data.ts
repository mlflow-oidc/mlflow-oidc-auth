export type NavLinkData = {
  label: string;
  href: string;
};

export type NavigationData = {
  mainLinks: NavLinkData[];
  userControls: NavLinkData[];
};

export const getNavigationData = (
  userName: string,
  basePath: string
): NavigationData => ({
  mainLinks: [
    { label: "MLFlow", href: "#" },
    {
      label: "GitHub",
      href: "https://github.com/mlflow-oidc/mlflow-oidc-auth",
    },
    {
      label: "Docs",
      href: "https://mlflow-oidc.github.io/mlflow-oidc-auth/#/",
    },
  ],
  userControls: [
    { label: `Hello, ${userName}`, href: "#" },
    { label: "Logout", href: `${basePath}/logout` },
  ],
});
