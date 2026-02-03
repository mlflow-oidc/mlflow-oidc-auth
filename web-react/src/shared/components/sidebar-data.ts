import type { NavLinkData } from "./navigation-data";
import {
  faUser,
  faScrewdriver,
  faSquareShareNodes,
  faMicroscope,
  faUserGroup,
  faHexagonNodes,
  faTrash,
  faWrench,
  faLink,
  faKey,
  faHexagonNodesBolt,
} from "@fortawesome/free-solid-svg-icons";

export const getSidebarData = (
  isAdmin: boolean,
  genAiGatewayEnabled: boolean,
): NavLinkData[] => {
  const baseLinks: NavLinkData[] = [
    { label: "Users", href: "/users", isInternalLink: true, icon: faUser },
    {
      label: "Service Accounts",
      href: "/service-accounts",
      isInternalLink: true,
      icon: faScrewdriver,
    },
    {
      label: "Groups",
      href: "/groups",
      isInternalLink: true,
      icon: faUserGroup,
    },
    {
      label: "Experiments",
      href: "/experiments",
      isInternalLink: true,
      icon: faMicroscope,
    },
    {
      label: "Prompts",
      href: "/prompts",
      isInternalLink: true,
      icon: faSquareShareNodes,
    },
    {
      label: "Models",
      href: "/models",
      isInternalLink: true,
      icon: faHexagonNodes,
    },
  ];

  let sidebarContent: NavLinkData[] = [...baseLinks];

  if (genAiGatewayEnabled) {
    const aiLinks: NavLinkData[] = [
      {
        label: "AI Endpoints",
        href: "/ai-gateway/endpoints",
        isInternalLink: true,
        icon: faLink,
      },
      {
        label: "AI Secrets",
        href: "/ai-gateway/secrets",
        isInternalLink: true,
        icon: faKey,
      },
      {
        label: "AI Models",
        href: "/ai-gateway/models",
        isInternalLink: true,
        icon: faHexagonNodesBolt,
      },
    ];
    sidebarContent = [...sidebarContent, ...aiLinks];
  }

  if (isAdmin) {
    const adminLinks: NavLinkData[] = [
      { label: "Trash", href: "/trash", isInternalLink: true, icon: faTrash },
      {
        label: "Webhooks",
        href: "/webhooks",
        isInternalLink: true,
        icon: faWrench,
      },
    ];

    sidebarContent = [...sidebarContent, ...adminLinks];
  }

  return sidebarContent;
};
