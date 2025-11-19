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
} from "@fortawesome/free-solid-svg-icons";

export const getSidebarData = (isAdmin: boolean): NavLinkData[] => {
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

    sidebarContent = [...baseLinks, ...adminLinks];
  }

  return sidebarContent;
};
