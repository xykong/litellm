"use client";

import { useLogin } from "@/app/(dashboard)/hooks/login/useLogin";
import { useUIConfig } from "@/app/(dashboard)/hooks/uiConfig/useUIConfig";
import LoadingScreen from "@/components/common_components/LoadingScreen";
import { getProxyBaseUrl } from "@/components/networking";
import { getCookie } from "@/utils/cookieUtils";
import { isJwtExpired } from "@/utils/jwtUtils";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Form, Input, Popover, Space, Typography } from "antd";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

function LoginPageContent() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const { data: uiConfig, isLoading: isConfigLoading } = useUIConfig();
  const loginMutation = useLogin();
  const router = useRouter();

  useEffect(() => {
    if (isConfigLoading) {
      return;
    }

    // Check if admin UI is disabled
    if (uiConfig?.admin_ui_disabled) {
      setIsLoading(false);
      return;
    }

    const rawToken = getCookie("token");
    if (rawToken && !isJwtExpired(rawToken)) {
      router.replace(`${getProxyBaseUrl()}/ui`);
      return;
    }

    if (uiConfig?.auto_redirect_to_sso) {
      router.push(`${getProxyBaseUrl()}/sso/key/generate`);
      return;
    }

    setIsLoading(false);
  }, [isConfigLoading, router, uiConfig]);

  const handleSubmit = () => {
    loginMutation.mutate(
      { username, password },
      {
        onSuccess: (data) => {
          router.push(data.redirect_url);
        },
      },
    );
  };

  const error = loginMutation.error instanceof Error ? loginMutation.error.message : null;
  const isLoginLoading = loginMutation.isPending;

  if (isConfigLoading || isLoading) {
    return <LoadingScreen />;
  }

  // Show disabled message if admin UI is disabled
  if (uiConfig?.admin_ui_disabled) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
            <div className="flex flex-col items-center mb-6">
              <div className="relative w-16 h-16 mb-4">
                <Image
                  src="/assets/logos/litellm_logo.jpg"
                  alt="Animal Gateway Logo"
                  fill
                  className="object-contain rounded-lg"
                  priority
                  unoptimized
                />
              </div>
              <h1 className="text-2xl font-semibold text-gray-900">Animal Gateway</h1>
            </div>

            <Alert
              message="Admin UI Disabled"
              description={
                <div className="space-y-2">
                  <p className="text-sm text-gray-600">
                    The Admin UI has been disabled by the administrator. To re-enable it, please update the following
                    environment variable:
                  </p>
                  <code className="block bg-gray-100 px-3 py-2 rounded text-xs font-mono text-gray-800">
                    DISABLE_ADMIN_UI=False
                  </code>
                </div>
              }
              type="warning"
              showIcon
              className="rounded-lg"
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="relative w-20 h-20 mb-6">
            <Image
              src="/assets/logos/litellm_logo.jpg"
              alt="Animal Gateway Logo"
              fill
              className="object-contain rounded-xl"
              priority
              unoptimized
            />
          </div>
          <h1 className="text-3xl font-semibold text-gray-900 tracking-tight">Animal Gateway</h1>
          <p className="mt-2 text-sm text-gray-600">Sign in to access your admin dashboard</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          {error && (
            <Alert
              message="Login Failed"
              description={error}
              type="error"
              showIcon
              className="mb-6 rounded-lg"
              role="alert"
            />
          )}

          <Form onFinish={handleSubmit} layout="vertical" requiredMark={false}>
            <Form.Item
              label={<span className="text-sm font-medium text-gray-700">Username</span>}
              name="username"
              rules={[{ required: true, message: "Username is required" }]}
            >
              <Input
                placeholder="Enter your username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isLoginLoading}
                size="large"
                className="rounded-lg"
                aria-label="Username"
              />
            </Form.Item>

            <Form.Item
              label={<span className="text-sm font-medium text-gray-700">Password</span>}
              name="password"
              rules={[{ required: true, message: "Password is required" }]}
            >
              <Input.Password
                placeholder="Enter your password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoginLoading}
                size="large"
                className="rounded-lg"
                aria-label="Password"
              />
            </Form.Item>

            <Form.Item className="mb-0">
              <Button
                type="primary"
                htmlType="submit"
                loading={isLoginLoading}
                disabled={isLoginLoading}
                block
                size="large"
                className="h-12 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200"
                style={{ minHeight: "44px" }}
              >
                {isLoginLoading ? "Signing in..." : "Sign in"}
              </Button>
            </Form.Item>
          </Form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-500">or</span>
            </div>
          </div>

          <Button
            type="default"
            block
            size="large"
            onClick={() => {
              window.location.href = `${getProxyBaseUrl()}/sso/happyelements/login`;
            }}
            className="h-12 rounded-lg font-medium border-gray-300 hover:border-gray-400 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200 cursor-pointer"
            style={{ minHeight: "44px" }}
            aria-label="Sign in with HappyElements SSO"
          >
            <span className="flex items-center justify-center">
              <svg
                className="w-5 h-5 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                />
              </svg>
              Sign in with HappyElements SSO
            </span>
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <LoginPageContent />;
}
