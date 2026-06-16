import { useEffect } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Outlet, useLocation } from "react-router-dom";
import { pageVariants, pageVariantsReduced } from "@/presentation/theme/motion";

export function AnimatedOutlet() {
  const location = useLocation();
  const reduced = useReducedMotion();
  const variants = reduced ? pageVariantsReduced : pageVariants;

  // Scroll restauração inteligente — apenas ao topo quando a rota MUDA,
  // não em transições de query/tab dentro da mesma página
  useEffect(() => {
    const isNewPage = !location.state?.noScroll;
    if (isNewPage) {
      const main = document.getElementById("main-content");
      if (main) {
        main.scrollTop = 0;
      }
      // Scroll window sempre suave para o topo ao mudar de página
      window.scrollTo({ top: 0, behavior: reduced ? "instant" : "smooth" });
    }
  }, [location.pathname, location.key, reduced]);

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        variants={variants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="w-full"
      >
        <Outlet />
      </motion.div>
    </AnimatePresence>
  );
}
