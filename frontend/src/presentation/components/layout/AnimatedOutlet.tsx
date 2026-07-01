import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";

/**
 * Renderiza a rota filha com remount garantido a cada navegação.
 * Sem Framer Motion — evita página invisível (opacity 0) em browsers reais.
 */
export function AnimatedOutlet() {
  const location = useLocation();

  useEffect(() => {
    const main = document.getElementById("main-scroll");
    if (!main || location.state?.noScroll) return;
    main.scrollTop = 0;
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.key, location.pathname, location.state]);

  return <Outlet key={location.key} />;
}
