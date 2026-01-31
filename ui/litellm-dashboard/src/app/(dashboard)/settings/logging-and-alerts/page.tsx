"use client";

import Settings from "@/components/settings";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const LoggingAndAlertsPage = () => {
  const { accessToken, userRole, userId, premiumUser } = useAuthorized();

  return <Settings accessToken={accessToken} userRole={userRole} userID={userId} premiumUser={premiumUser} />;
};

export default withAdminAuth(LoggingAndAlertsPage);
