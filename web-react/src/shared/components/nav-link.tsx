import React from "react";

interface NavLinkProps extends React.PropsWithChildren {
  href: string;
  onClick?: () => void;
}

const isExternalLink = (href: string): boolean => {
  return href.startsWith("http") || href.startsWith("https");
};

const NavLink: React.FC<NavLinkProps> = ({ href, children, onClick }) => {
  const baseClasses =
    "p-2 w-full sm:w-auto text-text-primary hover:text-text-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark text-lg sm:text-sm font-medium transition-colors text-left sm:text-center rounded-md";
  const isExternal = isExternalLink(href);

  const externalProps = isExternal
    ? { target: "_blank", rel: "noopener noreferrer" }
    : {};
  return (
    <a href={href} className={baseClasses} onClick={onClick} {...externalProps}>
      {children}
    </a>
  );
};

export default NavLink;
