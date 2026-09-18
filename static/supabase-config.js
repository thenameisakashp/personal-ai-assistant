const SUPABASE_URL = "https://ycfefwyfynoeoqhikmgn.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_DBg9-Yn-sdWOGKnEofPBkg_XksMQh_A";

const supabaseClient = window.supabase.createClient(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
);

console.log("Supabase connected:", !!supabaseClient);