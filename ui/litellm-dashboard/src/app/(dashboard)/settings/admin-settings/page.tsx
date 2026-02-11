"use client";

import AdminPanel from "@/components/AdminPanel";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { useState } from "react";
import useTeams from "@/app/(dashboard)/hooks/useTeams";
import { withAdminAuth } from "@/app/(dashboard)/components/withAdminAuth";

const AdminSettings = () => {
  return <AdminPanel />;
};

export default withAdminAuth(AdminSettings);
