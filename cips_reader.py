import pandas as pd
import numpy as np
import os
import glob
import re

class CIPSReader:
    def __init__(self, window=15, umbral_mv=250):
        self.window = window
        self.umbral_mv = umbral_mv

    def _clean_dataframe(self, df):
        numeric_cols = ["On Voltage", "Off Voltage", "Latitude", "Longitude", "Dist From Start"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                if "Voltage" in col:
                    mask = (df[col].abs() < 50) & (df[col].notna())
                    df.loc[mask, col] = df.loc[mask, col] * 1000
        return df

    def _filter_outliers(self, df):
        if "On Voltage" in df.columns:
            on_mv = df["On Voltage"]
            on_mediana = on_mv.rolling(self.window, center=True, min_periods=1).median()
            on_delta = abs(on_mv - on_mediana)
            on_outlier = on_delta > self.umbral_mv
            df["On_limpio"] = np.where(on_outlier, on_mediana, on_mv)
        else:
            df["On_limpio"] = np.nan

        if "Off Voltage" in df.columns:
            off_mv = df["Off Voltage"]
            off_mediana = off_mv.rolling(self.window, center=True, min_periods=1).median()
            off_delta = abs(off_mv - off_mediana)
            off_outlier = off_delta > self.umbral_mv
            df["Off_limpio"] = np.where(off_outlier, off_mediana, off_mv)
        else:
            df["Off_limpio"] = np.nan

        return df

    def read_files(self, archivos):
        if not archivos:
            return []

        hojas_dict = {"Survey Data": [], "DCP Data": []}

        for archivo in archivos:
            try:
                xls = pd.ExcelFile(archivo)
                if "Survey Data" in xls.sheet_names:
                    df_survey = pd.read_excel(xls, sheet_name="Survey Data")
                    df_survey["file_idx"] = len(hojas_dict["Survey Data"])
                    hojas_dict["Survey Data"].append(df_survey)
                if "DCP Data" in xls.sheet_names:
                    df_dcp = pd.read_excel(xls, sheet_name="DCP Data")
                    df_dcp["file_idx"] = len(hojas_dict["DCP Data"])
                    hojas_dict["DCP Data"].append(df_dcp)
            except Exception as e:
                print(f"Error reading {archivo}: {e}")

        if not hojas_dict["Survey Data"]:
            return []

        survey = pd.concat(hojas_dict["Survey Data"], ignore_index=True)
        
        # Merge DCP Data
        if hojas_dict["DCP Data"]:
            dcp = pd.concat(hojas_dict["DCP Data"], ignore_index=True)
            dcp = dcp.reset_index(drop=True)
            
            # Convert Value1 and Value2 to mV (from Volts)
            for col in ["Value1", "Value2"]:
                if col in dcp.columns:
                    dcp[col] = pd.to_numeric(dcp[col], errors='coerce') * 1000
                    
            if "Data No" in dcp.columns and "file_idx" in dcp.columns:
                # Group by file_idx and Data No to extract Far Ground, Near Ground, Metal IR
                dcp_features = []
                for (f_idx, data_no), group in dcp.groupby(["file_idx", "Data No"]):
                    d = {"file_idx": f_idx, "Data No": data_no, "Comments": "", "Device ID": "", 
                         "Far_ON": np.nan, "Far_OFF": np.nan, 
                         "Near_ON": np.nan, "Near_OFF": np.nan, 
                         "Metal_ON": np.nan, "Metal_OFF": np.nan}
                    
                    for _, row in group.iterrows():
                        anomaly = str(row.get("DCP/Feature/Anomaly", ""))
                        v1 = row.get("Value1", np.nan)
                        v2 = row.get("Value2", np.nan)
                        
                        if "Far Ground reading" in anomaly:
                            d["Far_ON"], d["Far_OFF"] = v1, v2
                        elif "Near Ground reading" in anomaly:
                            d["Near_ON"], d["Near_OFF"] = v1, v2
                        elif "Metal IR" in anomaly:
                            d["Metal_ON"], d["Metal_OFF"] = v1, v2
                            
                        # If the anomaly contains a PK marker or important keyword, make sure it's in the comments
                        if "+" in anomaly or "pk" in anomaly.lower() or "salto" in anomaly.lower() or "rio" in anomaly.lower() or "cruce" in anomaly.lower() or "cano" in anomaly.lower() or "caño" in anomaly.lower():
                            d["Comments"] += anomaly + " "
                            
                        # Concatenate Comments
                        if pd.notna(row.get("Comments")):
                            d["Comments"] += str(row["Comments"]) + " "
                        if pd.notna(row.get("Device ID")):
                            d["Device ID"] += str(row["Device ID"]) + " "
                            
                    dcp_features.append(d)
                
                if dcp_features:
                    df_dcp_feat = pd.DataFrame(dcp_features)
                    survey = survey.merge(df_dcp_feat, on=["file_idx", "Data No"], how="left")
                    
                    # Clean device ID
                    if "Device ID" in survey.columns:
                        survey["Device ID"] = survey["Device ID"].astype(str).str.replace(r'FEA.*', '', regex=True)
                        survey["Device ID"] = survey["Device ID"].astype(str).str.replace(r'DCP.*', '', regex=True)
                        survey["Comentarios"] = (survey["Device ID"].str.strip() + " | " + survey["Comments"].astype(str).str.strip()).str.strip(" |")
                    else:
                        survey["Comentarios"] = ""
                else:
                    survey["Comentarios"] = ""
        else:
            survey["Comentarios"] = ""

        # Clean and Filter
        survey = self._clean_dataframe(survey)
        survey = self._filter_outliers(survey)
        
        raw_results = []
        for i, row in survey.iterrows():
            if pd.isna(row.get("Latitude")) or pd.isna(row.get("Longitude")):
                continue
                
            raw_results.append({
                'file_idx': row.get("file_idx", 0),
                'abscisa_val': int(row.get("Dist From Start", 0)), 
                'abscisa': '', 
                'lat': row.get("Latitude"),
                'lon': row.get("Longitude"),
                'on_mv': row.get("On Voltage", np.nan),
                'off_mv': row.get("Off Voltage", np.nan),
                'on_limpio': row.get("On_limpio", np.nan),
                'off_limpio': row.get("Off_limpio", np.nan),
                'far_on': row.get("Far_ON", np.nan),
                'far_off': row.get("Far_OFF", np.nan),
                'near_on': row.get("Near_ON", np.nan),
                'near_off': row.get("Near_OFF", np.nan),
                'metal_on': row.get("Metal_ON", np.nan),
                'metal_off': row.get("Metal_OFF", np.nan),
                'observaciones': row.get("Comentarios", ""),
                'referencia': row.get("Comentarios", "") 
            })
            
        filtered_results = []
        last_lat, last_lon = None, None
        
        corrected_dist = 0
        last_raw_dist = raw_results[0]['abscisa_val'] if raw_results else 0
        
        for r in raw_results:
            current_raw_dist = r['abscisa_val']
            
            if r['lat'] == last_lat and r['lon'] == last_lon:
                # Same GPS as previous point -> equipment was stationary.
                # Update last_raw_dist so we don't count the wire unspooled while standing still
                last_raw_dist = current_raw_dist
                
                # Do not add a duplicate point, but preserve any important comments!
                obs_str = str(r['observaciones']) if pd.notna(r['observaciones']) else ""
                if obs_str.strip():
                    prev_obs = str(filtered_results[-1]['observaciones']) if pd.notna(filtered_results[-1]['observaciones']) else ""
                    if not prev_obs.strip():
                        filtered_results[-1]['observaciones'] = obs_str
                        filtered_results[-1]['referencia'] = str(r['referencia']) if pd.notna(r['referencia']) else ""
                    else:
                        filtered_results[-1]['observaciones'] = prev_obs + " | " + obs_str
                        filtered_results[-1]['referencia'] = str(filtered_results[-1]['referencia']) + " | " + str(r['referencia'])
                continue
                
            # GPS changed. Add the wire distance since the last point (which was the last duplicate if any)
            delta = current_raw_dist - last_raw_dist
            corrected_dist += delta
            
            # Update the point's abscisa_val to the corrected distance
            r['abscisa_val'] = corrected_dist
            filtered_results.append(r)
            
            last_lat, last_lon = r['lat'], r['lon']
            last_raw_dist = current_raw_dist
            
        return filtered_results
