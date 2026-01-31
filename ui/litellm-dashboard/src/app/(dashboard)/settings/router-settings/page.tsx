"use client";

import GeneralSettings from "@/components/general_settings";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const RouterSettingsPage = () => {
  const { accessToken, userRole, userId } = useAuthorized();

  return <GeneralSettings accessToken={accessToken} userRole={userRole} userID={userId} modelData={{}} />;
};

export default withAdminAuth(RouterSettingsPage);
