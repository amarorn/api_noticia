import type { ComponentType } from "react";
import {
  IconAlbum,
  IconCalendar,
  IconDashboard,
  IconHistory,
  IconLive,
  IconNewspaper,
  IconTrophy,
  IconUsers,
  IconWallet,
  IconZap,
} from "@/presentation/components/ui/Icons";

export interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  Icon: ComponentType<{ className?: string }>;
  description?: string;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    id: "copa",
    label: "Copa 2026",
    items: [
      {
        to: "/",
        label: "Dashboard",
        end: true,
        Icon: IconDashboard,
        description: "Palpites da rodada",
      },
      {
        to: "/jogos",
        label: "Jogos",
        Icon: IconCalendar,
        description: "Tabela oficial",
      },
      {
        to: "/amistosos",
        label: "Amistosos",
        Icon: IconCalendar,
        description: "Datas preparatórias",
      },
      {
        to: "/ao-vivo",
        label: "Ao vivo",
        Icon: IconLive,
        description: "Jogos Superbet live",
      },
      {
        to: "/grupos",
        label: "Grupos",
        Icon: IconTrophy,
        description: "Classificação simulada",
      },
      {
        to: "/convocacoes",
        label: "Convocações",
        Icon: IconUsers,
        description: "Elencos oficiais",
      },
      {
        to: "/album",
        label: "Álbum",
        Icon: IconAlbum,
        description: "Figurinhas KXL",
      },
      {
        to: "/predict",
        label: "Palpite avulso",
        Icon: IconZap,
        description: "Confronto oficial",
      },
      {
        to: "/validate",
        label: "Histórico",
        Icon: IconHistory,
        description: "Backtest WC",
      },
    ],
  },
  {
    id: "mais",
    label: "Mais",
    items: [
      {
        to: "/news",
        label: "Notícias",
        Icon: IconNewspaper,
        description: "Feed com sentimento",
      },
      {
        to: "/brasileirao",
        label: "Brasileirao",
        Icon: IconTrophy,
        description: "Rodada nacional",
      },
      {
        to: "/performance",
        label: "Performance",
        Icon: IconHistory,
        description: "ROI e analise de apostas",
      },
      {
        to: "/carteira",
        label: "Carteira",
        Icon: IconWallet,
        description: "CSV Superbet e reconciliação",
      },
    ],
  },
];

export const allNavItems = navGroups.flatMap((g) => g.items);
