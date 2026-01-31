"use client";

import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { isAdminRole } from "@/utils/roles";
import { Alert } from "antd";
import { useRouter } from "next/navigation";
import { ComponentType, useEffect } from "react";

interface WithAdminAuthOptions {
  redirectTo?: string;
  showAccessDenied?: boolean;
}

export function withAdminAuth<P extends object>(
  Component: ComponentType<P>,
  options: WithAdminAuthOptions = {}
) {
  const { redirectTo = "/", showAccessDenied = true } = options;

  return function ProtectedComponent(props: P) {
    const { userRole } = useAuthorized();
    const router = useRouter();

    useEffect(() => {
      if (userRole && !isAdminRole(userRole)) {
        if (redirectTo) {
          router.replace(redirectTo);
        }
      }
    }, [userRole, router]);

    if (!userRole) {
      return null;
    }

    if (!isAdminRole(userRole)) {
      if (showAccessDenied) {
        return (
          <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="max-w-md w-full">
              <Alert
                message="Access Denied"
                description="You do not have permission to access this page. Please contact your administrator."
                type="error"
                showIcon
              />
            </div>
          </div>
        );
      }
      return null;
    }

    return <Component {...props} />;
  };
}
