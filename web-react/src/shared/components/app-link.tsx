import React from "react";
import { Link } from "react-router";

interface AppLinkProps extends React.PropsWithChildren {
  href: string;
  onClick?: () => void;
  isInternalLink?: boolean;
  className?: string;
}

const isExternalLink = (href: string): boolean => {
  return href.startsWith("http") || href.startsWith("https");
};

const AppLink = ({
  href,
  children,
  onClick,
  isInternalLink,
  className,
}: AppLinkProps) => {
  const isExternal = isExternalLink(href);
  const externalProps = isExternal
    ? { target: "_blank", rel: "noopener noreferrer" }
    : {};

  if (isInternalLink) {
    return (
      <Link to={href} className={className} onClick={onClick}>
        {children}
      </Link>
    );
  }

  return (
    <a href={href} className={className} onClick={onClick} {...externalProps}>
      {children}
    </a>
  );
};

export default AppLink;
