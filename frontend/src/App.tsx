import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { OfflineProvider } from "@/context/OfflineContext";
import { I18nProvider } from "@/context/I18nContext";
import { AppRoutes } from "@/router/AppRoutes";

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <OfflineProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </OfflineProvider>
      </AuthProvider>
    </I18nProvider>
  );
}
