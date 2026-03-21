"use client";

import { useLogin } from "@/app/(dashboard)/hooks/login/useLogin";
import { useUIConfig } from "@/app/(dashboard)/hooks/uiConfig/useUIConfig";
import LoadingScreen from "@/components/common_components/LoadingScreen";
import { exchangeLoginCode, getProxyBaseUrl, switchToWorkerUrl } from "@/components/networking";
import { clearTokenCookies, getCookieFromDocument } from "@/utils/cookieUtils";
import { isJwtExpired } from "@/utils/jwtUtils";
import { consumeReturnUrl, getReturnUrl, isValidReturnUrl } from "@/utils/returnUrlUtils";
import { CloudServerOutlined } from "@ant-design/icons";
import { Alert, Button, Form, Input, Select } from "antd";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useWorker } from "@/hooks/useWorker";

function LoginPageContent() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const { data: uiConfig, isLoading: isConfigLoading } = useUIConfig();
  const loginMutation = useLogin();
  const router = useRouter();
  const { workers, selectWorker } = useWorker();
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const workerParam = params.get("worker");
    if (workerParam) {
      setSelectedWorkerId(workerParam);
    }
  }, []);

  useEffect(() => {
    if (isConfigLoading) {
      return;
    }

    if (uiConfig && uiConfig.admin_ui_disabled) {
      setIsLoading(false);
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const rawSsoCode = params.get("code");
    const ssoCode = rawSsoCode && /^[a-zA-Z0-9._~+/=-]+$/.test(rawSsoCode) ? rawSsoCode : null;
    if (ssoCode) {
      const rawWorkerUrl = localStorage.getItem("litellm_worker_url");
      const workerUrl = rawWorkerUrl && /^https?:\/\/.+/.test(rawWorkerUrl) ? rawWorkerUrl : null;
      exchangeLoginCode(ssoCode, workerUrl).then(() => {
        params.delete("code");
        const cleanSearch = params.toString();
        window.history.replaceState(null, "", window.location.pathname + (cleanSearch ? `?${cleanSearch}` : ""));
        router.replace("/ui/?login=success");
      });
      return;
    }

    const switchingWorker = params.has("worker");
    if (switchingWorker && uiConfig?.is_control_plane) {
      clearTokenCookies();
      setIsLoading(false);
      return;
    }

    const rawToken = getCookieFromDocument("token");
    if (rawToken && !isJwtExpired(rawToken)) {
      const returnUrl = consumeReturnUrl();
      if (returnUrl) {
        router.replace(returnUrl);
      } else {
        router.replace("/ui");
      }
      return;
    }

    if (uiConfig && uiConfig.auto_redirect_to_sso) {
      const returnUrl = getReturnUrl();
      let ssoUrl = `${getProxyBaseUrl()}/sso/key/generate`;
      if (returnUrl && isValidReturnUrl(returnUrl)) {
        ssoUrl += `?redirect_to=${encodeURIComponent(returnUrl)}`;
      }
      router.push(ssoUrl);
      return;
    }

    setIsLoading(false);
  }, [isConfigLoading, router, uiConfig]);

  const handleSubmit = () => {
    const selectedWorker = workers.find((w) => w.worker_id === selectedWorkerId);
    if (selectedWorker) {
      switchToWorkerUrl(selectedWorker.url);
    }

    loginMutation.mutate(
      { username, password, useV3: !!selectedWorker },
      {
        onSuccess: (data) => {
          if (selectedWorker) {
            selectWorker(selectedWorker.worker_id);
            router.push("/ui/?login=success");
          } else {
            const returnUrl = consumeReturnUrl();
            if (returnUrl) {
              router.push(returnUrl);
            } else {
              router.push(data.redirect_url);
            }
          }
        },
        onError: () => {
          if (selectedWorker) {
            switchToWorkerUrl(null);
          }
        },
      },
    );
  };

  const error = loginMutation.error instanceof Error ? loginMutation.error.message : null;
  const isLoginLoading = loginMutation.isPending;

  if (isConfigLoading || isLoading) {
    return <LoadingScreen />;
  }

  if (uiConfig && uiConfig.admin_ui_disabled) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
            <div className="flex flex-col items-center mb-6">
              <div className="relative w-16 h-16 mb-4">
                <Image
                  src="/assets/logos/animal_gateway_logo.jpg"
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
              src="/assets/logos/animal_gateway_logo.jpg"
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

          <Button
            type="primary"
            block
            size="large"
            onClick={() => {
              window.location.href = `${getProxyBaseUrl()}/sso/happyelements/login`;
            }}
            className="h-12 rounded-lg font-medium focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200 cursor-pointer"
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

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-500">or</span>
            </div>
          </div>

          <Form onFinish={handleSubmit} layout="vertical" requiredMark={false}>
            {uiConfig?.is_control_plane && workers.length > 0 && (
              <Form.Item label="Worker" style={{ marginBottom: 16 }}>
                <Select
                  value={selectedWorkerId || undefined}
                  onChange={(value) => setSelectedWorkerId(value)}
                  placeholder="Choose a worker to connect to"
                  size="large"
                  suffixIcon={<CloudServerOutlined />}
                  options={workers.map((w) => ({
                    label: w.name,
                    value: w.worker_id,
                  }))}
                />
              </Form.Item>
            )}

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
                type="default"
                htmlType="submit"
                loading={isLoginLoading}
                disabled={isLoginLoading}
                block
                size="large"
                className="h-12 rounded-lg font-medium border-gray-300 hover:border-gray-400 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200"
                style={{ minHeight: "44px" }}
              >
                {isLoginLoading ? "Signing in..." : "Sign in"}
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <LoginPageContent />;
}
