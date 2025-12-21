import React, { useState } from 'react';
import axios from 'axios';
import DatePicker, { registerLocale } from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";
import { zhCN } from 'date-fns/locale/zh-CN';
import { format } from 'date-fns';
import { Upload, FileSpreadsheet, Download, RefreshCcw, Briefcase, Coffee } from 'lucide-react';

registerLocale('zh-CN', zhCN);

function App() {
  const [file, setFile] = useState(null);
  const [holidays, setHolidays] = useState([]);
  const [makeupDays, setMakeupDays] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setMessage(null);
    }
  };

  const toggleDate = (date, type) => {
    if (!date) return;
    const list = type === 'holiday' ? holidays : makeupDays;
    const setList = type === 'holiday' ? setHolidays : setMakeupDays;
    const exists = list.find(d => d.getTime() === date.getTime());
    if (exists) setList(list.filter(d => d.getTime() !== date.getTime()));
    else setList([...list, date]);
  };

  const handleCalculate = async () => {
    if (!file) { setMessage({ type: 'error', text: '请先上传考勤表格！' }); return; }
    setLoading(true); setMessage(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('holidays', holidays.map(d => format(d, 'yyyy-MM-dd')).join(','));
    formData.append('makeup_days', makeupDays.map(d => format(d, 'yyyy-MM-dd')).join(','));

    try {
      const response = await axios.post('https://attendance-backend-rho.vercel.app/', formData, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${file.name.split('.')[0]}_结果.xlsx`);
      document.body.appendChild(link);
      link.click(); link.remove();
      setMessage({ type: 'success', text: '下载开始！' });
    } catch (error) {
      setMessage({ type: 'error', text: '连接失败，请检查Python后端是否运行' });
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8 font-sans text-gray-700">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold text-center text-gray-900">🐻 智能考勤计算器</h1>
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden border border-gray-100">
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-lg font-semibold mb-4">1. 上传考勤表</h2>
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center hover:border-indigo-400 bg-gray-50/50">
              <input type="file" onChange={handleFileChange} accept=".xlsx,.csv" className="hidden" id="file-upload" />
              <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                {file ? <div className="flex items-center gap-2 text-green-600"><FileSpreadsheet/>{file.name}</div> : <div className="flex flex-col items-center text-gray-400"><Upload className="w-10 h-10 mb-2"/>点击上传文件</div>}
              </label>
            </div>
          </div>
          <div className="p-6 grid md:grid-cols-2 gap-8">
            <div>
              <h2 className="text-lg font-semibold mb-2 text-red-600">2. 设节假日 (红)</h2>
              <div className="bg-red-50 p-4 rounded-xl border border-red-100 flex justify-center">
                <DatePicker inline locale="zh-CN" highlightDates={[{ "react-datepicker__day--highlighted-custom-1": holidays }]} onChange={(date) => toggleDate(date, 'holiday')} dayClassName={(date) => holidays.find(d => d.getTime() === date.getTime()) ? "bg-red-500 text-white rounded-full" : undefined} />
              </div>
            </div>
            <div>
              <h2 className="text-lg font-semibold mb-2 text-blue-600">3. 设补班 (蓝)</h2>
              <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 flex justify-center">
                <DatePicker inline locale="zh-CN" highlightDates={[{ "react-datepicker__day--highlighted-custom-2": makeupDays }]} onChange={(date) => toggleDate(date, 'makeup')} dayClassName={(date) => makeupDays.find(d => d.getTime() === date.getTime()) ? "bg-blue-600 text-white rounded-full" : undefined} />
              </div>
            </div>
          </div>
          <div className="p-6 bg-gray-50 flex flex-col items-center">
            {message && <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${message.type==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>{message.text}</div>}
            <button onClick={handleCalculate} disabled={loading} className={`w-full max-w-md py-3 text-white rounded-xl ${loading?'bg-indigo-400':'bg-indigo-600 hover:bg-indigo-700'} flex justify-center gap-2 shadow-lg`}>
              {loading ? <RefreshCcw className="animate-spin"/> : <Download/>} {loading ? '计算中...' : '开始计算并下载'}
            </button>
          </div>
        </div>
        <style>{`.react-datepicker__day--highlighted-custom-1 {background-color: #ef4444; color: white;} .react-datepicker__day--highlighted-custom-2 {background-color: #2563eb; color: white;} .react-datepicker {border:none; background:transparent;} .react-datepicker__header {background:transparent; border:none;}`}</style>
      </div>
    </div>
  );
}
export default App;