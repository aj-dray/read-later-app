// // Includes optimisations
// import Image from "next/image";

// <Image
//   src="/hero-desktop.png"
//   width={1000} // the actual image size
//   height={760}
//   className="hidden md:block" // hide on mobile and show on desktop; else use className="block md:hidden"
//   alt="Screenshots of the dashboard project showing desktop version"
// />;

// import clsx from "clsx";

// export default function InvoiceStatus({ status }: { status: string }) {
//   return (
//     <span
//       className={clsx(
//         "inline-flex items-center rounded-full px-2 py-1 text-xs",
//         {
//           "bg-gray-100 text-gray-500": status === "pending",
//           "bg-green-500 text-white": status === "paid",
//         },
//       )}
//     >
//       {status === "pending" ? (
//         <>
//           Pending
//           <ClockIcon className="ml-1 w-4 text-gray-500" />
//         </>
//       ) : null}
//       {status === "paid" ? (
//         <>
//           Paid
//           <CheckIcon className="ml-1 w-4 text-white" />
//         </>
//       ) : null}
//     </span>
//   );
// }

// // Layout shared components between children:
// import SideNav from "@/app/ui/dashboard/sidenav";

// export default function Layout({ children }: { children: React.ReactNode }) {
//   return (
//     <div className="flex h-screen flex-col md:flex-row md:overflow-hidden">
//       <div className="w-full flex-none md:w-64">
//         <SideNav />
//       </div>
//       <div className="flex-grow p-6 md:overflow-y-auto md:p-12">{children}</div>
//     </div>
//   );
// }
