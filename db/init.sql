-- Example schema: devices + alerts
-- Run this in Supabase SQL editor or via supabase CLI migrations.

-- Enable pgcrypto extension (for gen_random_uuid())
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Devices table
CREATE TABLE IF NOT EXISTS public.devices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  location text,
  owner_id uuid,
  created_at timestamptz DEFAULT now()
);

-- Alerts table
CREATE TABLE IF NOT EXISTS public.alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid REFERENCES public.devices(id) ON DELETE CASCADE,
  description text,
  image_url text,
  created_at timestamptz DEFAULT now()
);

-- Enable Row Level Security (RLS) on devices and alerts
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;

-- Policy: allow authenticated users to INSERT into devices (owner_id must match auth uid)
DROP POLICY IF EXISTS devices_insert_auth ON public.devices;
CREATE POLICY devices_insert_auth ON public.devices
  FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = owner_id);

-- Policy: allow authenticated users to SELECT their devices
DROP POLICY IF EXISTS devices_select_owner ON public.devices;
CREATE POLICY devices_select_owner ON public.devices
  FOR SELECT
  TO authenticated
  USING (owner_id = auth.uid());

-- Alerts: allow insert for authenticated users if device belongs to them
DROP POLICY IF EXISTS alerts_insert_auth ON public.alerts;
CREATE POLICY alerts_insert_auth ON public.alerts
  FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.devices d
      WHERE d.id = device_id AND d.owner_id = auth.uid()
    )
  );

-- Alerts: allow select for owners
DROP POLICY IF EXISTS alerts_select_owner ON public.alerts;
CREATE POLICY alerts_select_owner ON public.alerts
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.devices d
      WHERE d.id = device_id AND d.owner_id = auth.uid()
    )
  );
