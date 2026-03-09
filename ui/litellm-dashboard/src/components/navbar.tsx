import { useHealthReadinessDetails } from "@/app/(dashboard)/hooks/healthReadiness/useHealthReadinessDetails";
import { useDisableBouncingIcon } from "@/app/(dashboard)/hooks/useDisableBouncingIcon";
import { getProxyBaseUrl } from "@/components/networking";
import { useUIConfig } from "@/app/(dashboard)/hooks/uiConfig/useUIConfig";
import { useTheme } from "@/contexts/ThemeContext";
import { clearTokenCookies } from "@/utils/cookieUtils";
import { fetchProxySettings } from "@/utils/proxyUtils";
import { MenuFoldOutlined, MenuUnfoldOutlined, MessageOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import Link from "next/link";
import React, { useEffect, useState } from "react";
import { NotificationsBell } from "./Navbar/NotificationsBell/NotificationsBell";
import UserDropdown from "./Navbar/UserDropdown/UserDropdown";

interface NavbarProps {
  proxySettings: any;
  setProxySettings: React.Dispatch<React.SetStateAction<any>>;
  accessToken: string | null;
  isPublicPage: boolean;
  sidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
}

const Navbar: React.FC<NavbarProps> = ({
  proxySettings,
  setProxySettings,
  accessToken,
  isPublicPage = false,
  sidebarCollapsed = false,
  onToggleSidebar,
}) => {
  const baseUrl = getProxyBaseUrl();
  const [logoutUrl, setLogoutUrl] = useState("");
  const { data: uiConfig } = useUIConfig();
  const uiRoot = uiConfig?.server_root_path && uiConfig.server_root_path !== "/"
    ? uiConfig.server_root_path.replace(/\/+$/, "")
    : "";
  const chatHref = `${uiRoot}/ui/chat`;
  const { logoUrl } = useTheme();
  const { data: healthData } = useHealthReadinessDetails(accessToken);
  const version = healthData?.litellm_version;
  const disableBouncingIcon = useDisableBouncingIcon();

  const imageUrl = logoUrl || `${baseUrl}/get_image`;

  useEffect(() => {
    const initializeProxySettings = async () => {
      if (accessToken) {
        const settings = await fetchProxySettings(accessToken);
        console.log("response from fetchProxySettings", settings);
        if (settings) {
          setProxySettings(settings);
        }
      }
    };

    initializeProxySettings();
  }, [accessToken, setProxySettings]);

  useEffect(() => {
    setLogoutUrl(proxySettings?.PROXY_LOGOUT_URL || "");
  }, [proxySettings]);

  const handleLogout = () => {
    clearTokenCookies();
    window.location.href = logoutUrl;
  };

  return (
    <nav className="sticky top-0 z-10 border-b border-gray-200 bg-white">
      <div className="w-full">
        <div className="flex h-14 items-center px-4">
          <div className="flex flex-shrink-0 items-center">
            {onToggleSidebar && (
              <button
                type="button"
                onClick={onToggleSidebar}
                className="mr-2 flex h-9 w-9 items-center justify-center rounded-md text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900"
                title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                <span className="text-lg">{sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}</span>
              </button>
            )}

            <div className="flex items-center gap-2">
              <Link href={baseUrl ? baseUrl : "/"} className="flex items-center">
                <div className="relative">
                  <div className="flex h-10 max-w-48 items-center justify-center overflow-hidden">
                    <img
                      src={imageUrl}
                      alt="LiteLLM Brand"
                      className="h-auto max-h-full w-auto max-w-full object-contain"
                    />
                  </div>
                </div>
              </Link>
              {version && (
                <div className="relative">
                  {!disableBouncingIcon && (
                    <span
                      className="absolute -left-2 -top-1 animate-bounce text-lg"
                      style={{ animationDuration: "2s" }}
                      title="Thanks for using LiteLLM!"
                    >
                      🌑
                    </span>
                  )}
                  <Tag className="relative z-10 cursor-pointer text-xs font-medium">
                    <a
                      href="https://docs.litellm.ai/release_notes"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0"
                    >
                      v{version}
                    </a>
                  </Tag>
                </div>
              )}
            </div>
          </div>
          <div className="ml-auto flex items-center space-x-5">
            {/* Chat CTA — always visible, opens in new tab */}
            <a
              href={chatHref}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                borderRadius: 8,
                background: "#1677ff",
                color: "#fff",
                fontSize: 13,
                fontWeight: 600,
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.background = "#0958d9"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.background = "#1677ff"; }}
            >
              <MessageOutlined style={{ fontSize: 14 }} />
              Chat
              <span style={{
                fontSize: 9,
                fontWeight: 700,
                background: "#fff",
                color: "#1677ff",
                borderRadius: 3,
                padding: "1px 4px",
                letterSpacing: "0.05em",
              }}>
                NEW
              </span>
            </a>

            {!isPublicPage && (
              <div className="flex items-center gap-0.5 rounded-lg bg-gray-50 px-1 py-0 transition-colors hover:bg-gray-100">
                <NotificationsBell />
                <span className="mx-0.5 h-6 w-px shrink-0 bg-gray-200" aria-hidden />
                <UserDropdown onLogout={handleLogout} />
              </div>
            )}
          </div>
          {/* Dark mode toggle: keep disabled until the dashboard supports dark styles end-to-end. */}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
