export type TransactionType = 'sale' | 'rent'
export type PropertyType = 'apartment' | 'house' | 'villa'
export type Amenity = 'parking' | 'elevator' | 'storage'

export interface Criteria {
  transaction_type?: TransactionType | null
  city?: string | null
  neighborhood?: string | null
  property_type?: PropertyType | null
  max_price_toman?: number | null
  max_deposit_toman?: number | null
  max_monthly_rent_toman?: number | null
  min_area_sqm?: number | null
  max_area_sqm?: number | null
  bedrooms?: number | null
  must_have_amenities: Amenity[]
  preferred_amenities: Amenity[]
  transit_max_minutes?: number | null
  transit_preference_minutes?: number | null
  emphasis: string[]
}

export interface Property {
  id: number
  property_id: string
  group_key: string
  advertisement_count: number
  transaction_type: TransactionType
  property_type: PropertyType
  city: string
  neighborhood: string
  latitude: number
  longitude: number
  area_sqm: number
  bedrooms: number
  sale_price_toman: number | null
  deposit_toman: number | null
  monthly_rent_toman: number | null
  price_per_sqm_toman: number | null
  floor_number: number | null
  total_floors: number | null
  building_age_years: number | null
  parking: boolean
  elevator: boolean
  storage: boolean
  transit_mode: string | null
  transit_station: string | null
  transit_distance_m: number | null
  transit_walk_minutes: number | null
  neighborhood_info: string
  description: string
  images: string[]
  listing_date: string
  source_name: string
  source_url: string | null
  title: string
  synthetic: boolean
  match_score: number
  match_reasons: string[]
  unmet_preferences: string[]
  failed_constraints?: string[]
  sources: { id: number; source_name: string; title: string; source_url: string | null; sale_price_toman?: number | null; deposit_toman?: number | null; monthly_rent_toman?: number | null }[]
}

export interface SearchResponse {
  results: Property[]
  total: number
  near_matches: Property[]
  near_matches_total: number
  criteria: Criteria
  sort_by: string
  synthetic: boolean
}

export interface Metadata {
  cities: string[]
  neighborhoods: Record<string, string[]>
  property_types: { value: PropertyType; label: string }[]
  amenities: { value: Amenity; label: string }[]
  ai: { cheap: boolean; standard: boolean; premium: boolean }
  advertisements: number
  unique_properties: number
  synthetic_data: boolean
}

export const emptyCriteria = (): Criteria => ({
  transaction_type: 'sale', must_have_amenities: [], preferred_amenities: [], emphasis: [],
})
