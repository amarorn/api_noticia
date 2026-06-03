import { useEffect } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Outlet, useLocation } from "react-router-dom";
import { pageVariants, pageVariantsReduced } from "@/presentation/theme/motion";

export function AnimatedOutlet() {
  const location = useLocation();
  const reduced = useReducedMotion();
  const variants = reduced ? pageVariantsReduced : pageVariants;

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  }, [location.pathname, reduced]);

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
