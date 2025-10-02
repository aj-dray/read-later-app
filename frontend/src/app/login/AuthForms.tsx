"use client";

import { useState, useEffect, useActionState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

import { type AuthActionState, signInAction, signUpAction } from "./actions";

const INITIAL_STATE: AuthActionState = { status: "idle" };

function LoginTab({
  activeTab,
  setActiveTab,
  text,
}: {
  activeTab: "login" | "signup";
  setActiveTab: (tab: "login" | "signup") => void;
  text: string;
}) {
  const tabValue = text === "login" ? "login" : "signup";
  return (
    <button
      onClick={() => setActiveTab(tabValue as "login" | "signup")}
      className={`relative flex h-10 w-[60px] items-center justify-center rounded-[20px] text-xs font-bold transition-all duration-300 z-10 ${
        activeTab === tabValue
          ? "text-white"
          : "text-black/75 hover:bg-gray-200"
      }`}
    >
      {text}
    </button>
  );
}

export default function AuthForms() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"login" | "signup">("login");
  const [signInState, signIn, signingIn] = useActionState(
    signInAction,
    INITIAL_STATE,
  );
  const [signUpState, signUp, signingUp] = useActionState(
    signUpAction,
    INITIAL_STATE,
  );

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | undefined>(
    undefined,
  );
  const [requestingDemo, setRequestingDemo] = useState(false);
  const [demoCredentials, setDemoCredentials] = useState<{
    username: string;
    password: string;
  } | null>(null);
  const [usernameHasText, setUsernameHasText] = useState(false);
  const [passwordHasText, setPasswordHasText] = useState(false);

  const currentActionState = activeTab === "login" ? signInState : signUpState;

  useEffect(() => {
    if (signInState.status === "success" || signUpState.status === "success") {
      router.push("/queue");
    }
    if (currentActionState.status === "error") {
      setErrorMessage(currentActionState.message);
    }
  }, [router, signInState, signUpState, currentActionState]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    if (name === "username") {
      setUsername(value);
      setUsernameHasText(value.length > 0);
    }
    if (name === "password") {
      setPassword(value);
      setPasswordHasText(value.length > 0);
    }
    if (errorMessage) {
      setErrorMessage(undefined);
    }
  };

  const handleDemoRequest = async () => {
    setErrorMessage(undefined);
    setRequestingDemo(true);
    setDemoCredentials(null);
    try {
      const response = await fetch("/api/demo/request", { method: "POST" });
      const payload = (await response.json()) as
        | { username: string; password: string }
        | { error?: string };
      if (!response.ok) {
        const msg =
          "error" in payload && payload.error
            ? payload.error
            : "Unable to provision demo account.";
        setErrorMessage(msg);
      } else if ("username" in payload && "password" in payload) {
        setDemoCredentials({
          username: payload.username,
          password: payload.password,
        });
      } else {
        setErrorMessage("Unexpected response from server.");
      }
    } catch (err) {
      console.error("Failed to request demo", err);
      setErrorMessage("Failed to request demo.");
    } finally {
      setRequestingDemo(false);
    }
  };

  // Clear form state when switching tabs
  useEffect(() => {
    setUsername("");
    setPassword("");
    setErrorMessage(undefined);
    setUsernameHasText(false);
    setPasswordHasText(false);
  }, [activeTab]);

  const isLoading = signingIn || signingUp;
  const showSubmit = !isLoading && username.length > 0 && password.length > 0;
  const showContent = !!errorMessage || showSubmit || activeTab === "signup";

  return (
    <div className="flex flex-col gap-[10px] items-center">
      {/* Tab Navigation */}
      <div className="panel-dark flex gap-[15px] p-[5px] relative z-10 transition-all drop-shadow-lg duration-300 ease-in-out rounded-[25px]">
        {/* Animated Black Pill */}
        <motion.div
          className="absolute h-10 w-[60px] rounded-[20px] bg-black/75 drop-shadow-md"
          animate={{
            x: activeTab === "login" ? 0 : 75,
          }}
          transition={{
            type: "spring",
            stiffness: 300,
            damping: 30,
          }}
        />
        <LoginTab
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          text="login"
        />
        <LoginTab
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          text="sign up"
        />
      </div>

      {/* Form Container */}
      <motion.div
        className="rounded-[25px] panel-light p-[15px] relative z-0"
        animate={{
          height: showContent ? "auto" : "auto",
        }}
        transition={{
          duration: 0.3,
          ease: "easeInOut",
        }}
      >
        <div className="flex flex-col items-center gap-[10px]">
          {activeTab === "login" ? (
            <form action={signIn} className="flex flex-col gap-[10px]">
              {/* Username Field */}
              <div className="flex h-[40px] w-[200px] items-center justify-center rounded-[20px] bg-white/75 backdrop-blur-md px-[15px] hover:scale-105 hover:drop-shadow-md hover:bg-white/75 focus-within:scale-105 focus-within:drop-shadow-md focus-within:bg-white/75 focus-within:hover:bg-white/75 transition-all duration-200 group">
                <input
                  name="username"
                  type="text"
                  placeholder="username"
                  autoComplete="username"
                  required
                  disabled={isLoading}
                  className={`h-[40px] w-full bg-transparent ${usernameHasText ? "text-left" : "text-left focus:text-left"} text-xs text-black placeholder-black/40 group-hover:placeholder-black/20 focus:placeholder-black/20 focus:group-hover:placeholder-black/20 focus:outline-none disabled:opacity-50 transition-all duration-200`}
                  value={username}
                  onChange={handleInputChange}
                />
              </div>

              {/* Password Field */}
              <div className="flex h-[40px] w-[200px] items-center justify-center rounded-[20px] bg-white/75 backdrop-blur-md px-[15px] hover:scale-105 hover:drop-shadow-md focus-within:scale-105 focus-within:drop-shadow-md transition-all duration-200 group">
                <input
                  name="password"
                  type="password"
                  placeholder="password"
                  autoComplete="current-password"
                  required
                  disabled={isLoading}
                  className={`h-[40px] w-full bg-transparent ${passwordHasText ? "text-left" : "text-left focus:text-left"} text-xs text-black placeholder-black/40 group-hover:placeholder-black/20 focus:placeholder-black/20 focus:group-hover:placeholder-black/20 focus:outline-none disabled:opacity-50 transition-all duration-200`}
                  value={password}
                  onChange={handleInputChange}
                />
              </div>

              {/* Error Message / Submit Button */}
              {(errorMessage || showSubmit) && (
                <motion.div
                  className="flex items-center justify-center pt-[5px] h-fit"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{
                    duration: 0.3,
                    ease: "easeInOut",
                  }}
                >
                  {errorMessage ? (
                    <p className="flex items-center justify-center text-center text-xs text-red-600">
                      {errorMessage}
                    </p>
                  ) : (
                    showSubmit && (
                      <button
                        type="submit"
                        disabled={isLoading}
                        className="flex h-[30px] w-[90px] items-center justify-center rounded-full text-xs transition-all duration-300 ease-in-out hover:text-white/95 hover:bg-black/75  font-bold text-black hover:drop-shadow-md hover:scale-105 disabled:opacity-50"
                      >
                        {isLoading ? "..." : "enter ⏎"}
                      </button>
                    )
                  )}
                </motion.div>
              )}
            </form>
          ) : (
            <div className="flex flex-col gap-[10px] items-center">
              {/* Sign Up Tab - Demo Request */}
              {!demoCredentials && (
                <button
                  onClick={handleDemoRequest}
                  disabled={requestingDemo}
                  className="flex h-[40px] w-[200px] items-center justify-center rounded-[20px] bg-purple-500/70 backdrop-blur-md text-white text-xs font-medium hover:bg-purple-600/90 hover:scale-102 hover:drop-shadow-md transition-all duration-200 disabled:opacity-60"
                >
                  {requestingDemo ? "requesting..." : "request demo login"}
                </button>
              )}
              {demoCredentials && (
                <div className="flex flex-col items-center gap-[6px] text-xs text-black/80">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">username:</span>
                    <span className="rounded-[12px] bg-white/75 px-2 py-1 font-mono text-black/90 select-text cursor-text">
                      {demoCredentials.username}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">password:</span>
                    <span className="rounded-[12px] bg-white/75 px-2 py-1 font-mono text-black/90 select-text cursor-text">
                      {demoCredentials.password}
                    </span>
                  </div>
                  <div className="text-[10px] text-black/60 p-[10px] w-[250px]">
                    Copy these credential and return to the login form. Note
                    that after page refresh these will not be shown again.
                  </div>
                </div>
              )}

              {/* Error Message for Sign Up */}
              {errorMessage && (
                <motion.div
                  className="flex items-center justify-center overflow-hidden"
                  animate={{
                    height: "auto",
                    opacity: 1,
                  }}
                  transition={{
                    duration: 0.3,
                    ease: "easeInOut",
                  }}
                >
                  <p className="flex items-center justify-center text-center text-xs text-red-600">
                    {errorMessage}
                  </p>
                </motion.div>
              )}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
