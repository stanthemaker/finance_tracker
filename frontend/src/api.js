import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export const scanStatements   = ()        => api.post("/scan").then((r) => r.data);
export const fetchMonths      = ()        => api.get("/months").then((r) => r.data);
export const fetchDashboard   = (month)   => api.get(`/dashboard/${month}`).then((r) => r.data);
export const fetchAverages    = ()        => api.get("/averages").then((r) => r.data);
export const fetchTransactions = (params) => api.get("/transactions", { params }).then((r) => r.data);
export const updateTransaction = (id, data) => api.patch(`/transactions/${id}`, data);
export const fetchSettings    = ()        => api.get("/settings").then((r) => r.data);
export const updateSettings   = (data)   => api.put("/settings", data);
export const fetchAdvice      = (month)   => api.get(`/advice/${month}`).then((r) => r.data);
export const fetchStatements  = ()        => api.get("/statements").then((r) => r.data);
export const deleteStatement  = (id)     => api.delete(`/statements/${id}`);
export const fetchCategories  = ()        => api.get("/categories").then((r) => r.data);
export const fetchNetWorth    = ()        => api.get("/networth").then((r) => r.data);
export const deletePortfolio  = (id)     => api.delete(`/portfolio/${id}`);
