/* =========================================================
   IRAA — LOGIN / SIGN UP
   SUPABASE AUTHENTICATION
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    console.log("Iraa: script.js loaded");


    /* =====================================================
       SUPABASE CHECK
       ===================================================== */

    if (typeof supabaseClient === "undefined") {

        console.error(
            "Iraa: Supabase client was not found."
        );

        return;
    }

    console.log(
        "Iraa: Supabase client ready"
    );


    /* =====================================================
       ELEMENTS
       ===================================================== */

    const loginTab =
        document.getElementById("login-tab");

    const signupTab =
        document.getElementById("signup-tab");

    const loginForm =
        document.getElementById("login-form");

    const signupForm =
        document.getElementById("signup-form");

    const loginButton =
        document.getElementById("login-btn");

    const signupButton =
        document.getElementById("signup-btn");

    const loginEmail =
        document.getElementById("login-email");

    const loginPassword =
        document.getElementById("login-password");

    const signupName =
        document.getElementById("signup-name");

    const signupEmail =
        document.getElementById("signup-email");

    const signupPassword =
        document.getElementById("signup-password");

    const signupConfirmPassword =
        document.getElementById(
            "signup-confirm-password"
        );

    const forgotPassword =
        document.getElementById("forgot-password");

    const googleLogin =
        document.getElementById("google-login");

    const githubLogin =
        document.getElementById("github-login");

    const showSignupButton =
        document.getElementById("show-signup");

    const showLoginButton =
        document.getElementById("show-login");

    const authMessage =
        document.getElementById("auth-message");


    /* =====================================================
       MESSAGE
       ===================================================== */

    function showMessage(
        message,
        type = "error"
    ) {

        if (!authMessage) {
            console.log(message);
            return;
        }

        authMessage.textContent =
            message;

        authMessage.style.color =
            type === "success"
                ? "#8cffc1"
                : "#ff8998";
    }


    function clearMessage() {

        if (authMessage) {
            authMessage.textContent = "";
        }
    }


    /* =====================================================
       SHOW LOGIN
       ===================================================== */

    function showLogin() {

        console.log(
            "Iraa: Login page selected"
        );

        clearMessage();

        if (loginForm) {

            loginForm.style.display =
                "block";
        }

        if (signupForm) {

            signupForm.style.setProperty(
                "display",
                "none",
                "important"
            );

            signupForm.classList.remove(
                "signup-visible"
            );
        }

        loginTab?.classList.add(
            "active"
        );

        signupTab?.classList.remove(
            "active"
        );
    }


    /* =====================================================
       SHOW SIGN UP
       ===================================================== */

    function showSignup() {

        console.log(
            "Iraa: Sign Up page selected"
        );

        clearMessage();

        if (loginForm) {

            loginForm.style.setProperty(
                "display",
                "none",
                "important"
            );
        }

        if (signupForm) {

            signupForm.classList.add(
                "signup-visible"
            );

            signupForm.style.setProperty(
                "display",
                "block",
                "important"
            );
        }

        loginTab?.classList.remove(
            "active"
        );

        signupTab?.classList.add(
            "active"
        );
    }


    /* =====================================================
       TAB BUTTONS
       ===================================================== */

    loginTab?.addEventListener(
        "click",
        event => {

            event.preventDefault();

            showLogin();
        }
    );


    signupTab?.addEventListener(
        "click",
        event => {

            event.preventDefault();

            showSignup();
        }
    );


    showSignupButton?.addEventListener(
        "click",
        event => {

            event.preventDefault();

            showSignup();
        }
    );


    showLoginButton?.addEventListener(
        "click",
        event => {

            event.preventDefault();

            showLogin();
        }
    );


    /* =====================================================
       BUTTON LOADING
       ===================================================== */

    function setLoading(
        button,
        loading,
        text
    ) {

        if (!button) return;

        if (loading) {

            button.dataset.originalText =
                button.innerHTML;

            button.disabled =
                true;

            button.innerHTML =
                text;

        } else {

            button.disabled =
                false;

            if (
                button.dataset.originalText
            ) {

                button.innerHTML =
                    button.dataset.originalText;
            }
        }
    }


    /* =====================================================
       LOGIN
       ===================================================== */

    async function loginUser() {

        clearMessage();

        const email =
            loginEmail?.value.trim() || "";

        const password =
            loginPassword?.value || "";


        if (!email) {

            showMessage(
                "Please enter your email."
            );

            loginEmail?.focus();

            return;
        }


        if (!password) {

            showMessage(
                "Please enter your password."
            );

            loginPassword?.focus();

            return;
        }


        setLoading(
            loginButton,
            true,
            "Logging in..."
        );


        try {

            console.log(
                "Iraa: Signing in with Supabase..."
            );


            const {
                data,
                error
            } =
                await supabaseClient.auth
                    .signInWithPassword({

                        email: email,

                        password: password
                    });


            if (error) {
                throw error;
            }


            console.log(
                "Iraa: Login successful"
            );


            /*
             IMPORTANT:
             Do NOT show the old #app here.

             Go to the separate application page.
            */

            window.location.href =
                "/app";


        } catch (error) {

            console.error(
                "Iraa login error:",
                error
            );


            let message =
                error.message ||
                "Unable to login.";


            if (
                message
                    .toLowerCase()
                    .includes(
                        "email not confirmed"
                    )
            ) {

                message =
                    "Please confirm your email before logging in.";
            }


            showMessage(
                message
            );


        } finally {

            setLoading(
                loginButton,
                false,
                "Login"
            );
        }
    }


    /* =====================================================
       LOGIN EVENTS
       ===================================================== */

    loginButton?.addEventListener(
        "click",
        event => {

            event.preventDefault();

            loginUser();
        }
    );


    loginForm?.addEventListener(
        "submit",
        event => {

            event.preventDefault();

            loginUser();
        }
    );


    /* =====================================================
       SIGN UP
       ===================================================== */

    async function signupUser() {

        clearMessage();

        const name =
            signupName?.value.trim() || "";

        const email =
            signupEmail?.value.trim() || "";

        const password =
            signupPassword?.value || "";

        const confirmPassword =
            signupConfirmPassword?.value || "";


        /* ---------------------------------------------
           VALIDATION
        --------------------------------------------- */

        if (!name) {

            showMessage(
                "Please enter your name."
            );

            signupName?.focus();

            return;
        }


        if (!email) {

            showMessage(
                "Please enter your email."
            );

            signupEmail?.focus();

            return;
        }


        if (!password) {

            showMessage(
                "Please create a password."
            );

            signupPassword?.focus();

            return;
        }


        if (password.length < 6) {

            showMessage(
                "Password must be at least 6 characters."
            );

            signupPassword?.focus();

            return;
        }


        if (
            password !==
            confirmPassword
        ) {

            showMessage(
                "Passwords do not match."
            );

            signupConfirmPassword?.focus();

            return;
        }


        setLoading(
            signupButton,
            true,
            "Creating account..."
        );


        try {

            console.log(
                "Iraa: Creating Supabase account..."
            );


            const {
                data,
                error
            } =
                await supabaseClient.auth
                    .signUp({

                        email: email,

                        password: password,

                        options: {

                            data: {

                                name: name,

                                full_name: name
                            }
                        }
                    });


            if (error) {
                throw error;
            }


            console.log(
                "Iraa: Supabase account created",
                data
            );


            /*
             Email confirmation enabled:
             session will normally be null.
            */

            if (
                data.user &&
                !data.session
            ) {

                showMessage(
                    "Account created! Please check your email to verify your account.",
                    "success"
                );

                return;
            }


            /*
             Email confirmation disabled:
             user can enter immediately.
            */

            if (data.session) {

                showMessage(
                    "Account created successfully!",
                    "success"
                );

                setTimeout(
                    () => {

                        window.location.href =
                            "/app";

                    },
                    500
                );

                return;
            }


            showMessage(
                "Account created. Please check your email.",
                "success"
            );


        } catch (error) {

            console.error(
                "Iraa signup error:",
                error
            );


            showMessage(
                error.message ||
                "Unable to create account."
            );


        } finally {

            setLoading(
                signupButton,
                false,
                "Create account"
            );
        }
    }


    /* =====================================================
       SIGN UP EVENTS
       ===================================================== */

    signupButton?.addEventListener(
        "click",
        event => {

            event.preventDefault();

            signupUser();
        }
    );


    signupForm?.addEventListener(
        "submit",
        event => {

            event.preventDefault();

            signupUser();
        }
    );


    /* =====================================================
       PASSWORD VISIBILITY
       ===================================================== */

    window.togglePassword =
        function (
            inputId,
            button
        ) {

            const input =
                document.getElementById(
                    inputId
                );


            if (!input) {
                return;
            }


            if (
                input.type ===
                "password"
            ) {

                input.type =
                    "text";

            } else {

                input.type =
                    "password";
            }
        };


    /* =====================================================
       FORGOT PASSWORD
       ===================================================== */

    forgotPassword?.addEventListener(
        "click",
        async event => {

            event.preventDefault();

            clearMessage();

            const email =
                loginEmail?.value.trim() || "";


            if (!email) {

                showMessage(
                    "Enter your email first."
                );

                loginEmail?.focus();

                return;
            }


            try {

                const {
                    error
                } =
                    await supabaseClient.auth
                        .resetPasswordForEmail(
                            email,
                            {
                                redirectTo:
                                    window.location.origin
                            }
                        );


                if (error) {
                    throw error;
                }


                showMessage(
                    "Password reset email sent!",
                    "success"
                );


            } catch (error) {

                console.error(
                    "Iraa password reset error:",
                    error
                );


                showMessage(
                    error.message ||
                    "Unable to send password reset email."
                );
            }
        }
    );


    /* =====================================================
       GOOGLE
       ===================================================== */

    googleLogin?.addEventListener(
        "click",
        async event => {

            event.preventDefault();

            try {

                const {
                    error
                } =
                    await supabaseClient.auth
                        .signInWithOAuth({

                            provider: "google",

                            options: {

                                redirectTo:
                                    window.location.origin
                                    + "/app"
                            }
                        });


                if (error) {
                    throw error;
                }


            } catch (error) {

                console.error(
                    "Google login error:",
                    error
                );

                showMessage(
                    error.message ||
                    "Google login failed."
                );
            }
        }
    );


    /* =====================================================
       GITHUB
       ===================================================== */

    githubLogin?.addEventListener(
        "click",
        async event => {

            event.preventDefault();

            try {

                const {
                    error
                } =
                    await supabaseClient.auth
                        .signInWithOAuth({

                            provider: "github",

                            options: {

                                redirectTo:
                                    window.location.origin
                                    + "/app"
                            }
                        });


                if (error) {
                    throw error;
                }


            } catch (error) {

                console.error(
                    "GitHub login error:",
                    error
                );

                showMessage(
                    error.message ||
                    "GitHub login failed."
                );
            }
        }
    );


    /* =====================================================
       SESSION CHECK
       ===================================================== */

    async function checkCurrentUser() {

        try {

            console.log(
                "Iraa: Checking current Supabase session..."
            );


            const {
                data,
                error
            } =
                await supabaseClient.auth
                    .getSession();


            if (error) {
                throw error;
            }


            if (
                data?.session?.user
            ) {

                console.log(
                    "Iraa: Active session found"
                );

                /*
                 If already logged in,
                 go directly to the separate app.
                */

                window.location.href =
                    "/app";

            } else {

                console.log(
                    "Iraa: No active session"
                );

                /*
                 Stay on Login page.
                 Do NOT touch #app.
                */

                showLogin();
            }


        } catch (error) {

            console.error(
                "Iraa session error:",
                error
            );

            showLogin();
        }
    }


    /* =====================================================
       AUTH STATE
       ===================================================== */

    supabaseClient.auth.onAuthStateChange(
        (event, session) => {

            console.log(
                "Iraa Auth Event:",
                event
            );


            if (
                event ===
                "SIGNED_IN"
            ) {

                window.location.href =
                    "/app";
            }


            if (
                event ===
                "SIGNED_OUT"
            ) {

                window.location.href =
                    "/";
            }
        }
    );


    /* =====================================================
       ENTER KEY
       ===================================================== */

    document.addEventListener(
        "keydown",
        event => {

            if (
                event.key !== "Enter"
            ) {
                return;
            }


            const active =
                document.activeElement;


            if (!active) {
                return;
            }


            if (
                active.id ===
                    "login-email" ||
                active.id ===
                    "login-password"
            ) {

                loginUser();

                return;
            }


            if (
                active.id ===
                    "signup-name" ||
                active.id ===
                    "signup-email" ||
                active.id ===
                    "signup-password" ||
                active.id ===
                    "signup-confirm-password"
            ) {

                signupUser();
            }
        }
    );


    /* =====================================================
       START
       ===================================================== */

    showLogin();

    checkCurrentUser();


    console.log(
        "Iraa: Authentication system ready."
    );

});