import { supabase } from './supabaseClient';

// Example: read recent devices
export async function getDevices() {
  const { data, error } = await supabase
    .from('devices')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(50);
  return { data, error };
}

// Example: insert device
export async function addDevice(payload: { name: string; location?: string }) {
  const { data, error } = await supabase.from('devices').insert([payload]);
  return { data, error };
}

// Example: insert an alert (with optional image URL)
export async function addAlert(payload: { device_id: string; description?: string; image_url?: string }) {
  const { data, error } = await supabase.from('alerts').insert([payload]);
  return { data, error };
}
